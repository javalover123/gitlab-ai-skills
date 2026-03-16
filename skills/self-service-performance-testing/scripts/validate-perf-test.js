#!/usr/bin/env node

/**
 * k6 Performance Test Validator
 *
 * Static analysis of k6 test files to catch common anti-patterns.
 * Zero dependencies - runs with Node.js only.
 *
 * Usage:
 *   node validate-perf-test.js path/to/test.js
 *   node validate-perf-test.js path/to/test.js --json
 *
 * Exit codes:
 *   0 - all checks passed (warnings may be present)
 *   1 - one or more ERROR-level issues found
 *   2 - file not found or unreadable
 */

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const jsonOutput = args.includes('--json');
const filePath = args.find(a => !a.startsWith('--'));

if (!filePath) {
  console.error('Usage: validate-perf-test.js <path-to-k6-test.js> [--json]');
  process.exit(2);
}

let content;
try {
  content = fs.readFileSync(path.resolve(filePath), 'utf-8');
} catch (err) {
  console.error(`Cannot read file: ${filePath}`);
  process.exit(2);
}

const lines = content.split('\n');
const findings = [];

function addFinding(severity, check, message, lineNum) {
  findings.push({ severity, check, message, line: lineNum || null });
}

// Helper: find line number of first match
function findLine(pattern) {
  for (let i = 0; i < lines.length; i++) {
    if (pattern.test(lines[i])) return i + 1;
  }
  return null;
}

// Helper: check if a line is inside the default function (rough heuristic).
//
// KNOWN LIMITATION: This walks backward from the line to find the nearest
// enclosing export. It will misidentify code inside helper functions that
// are defined AFTER `export default function` in the file, or inside arrow
// functions assigned to variables. This is a trade-off of regex-based
// analysis (zero dependencies) vs. full AST parsing. It correctly handles
// ~90% of typical k6 test structures where helpers are defined before the
// default export.
function isInDefaultFunction(lineIndex) {
  // Walk backward to find 'export default function'
  for (let i = lineIndex; i >= 0; i--) {
    if (/export\s+default\s+function/.test(lines[i])) return true;
    if (/export\s+function\s+setup/.test(lines[i])) return false;
    if (/export\s+function\s+teardown/.test(lines[i])) return false;
  }
  return false;
}

// ─── CHECK 1: Thresholds exist ───────────────────────────────────────────────
const hasThresholds = /thresholds\s*:\s*\{/.test(content);
if (!hasThresholds) {
  addFinding('ERROR', 'thresholds-exist',
    'No thresholds defined. Without thresholds, k6 always exits 0 even if the system is failing. Add thresholds to options.');
} else {
  // CHECK 1a: Thresholds use p95 or p99 (not just avg)
  const thresholdsBlock = content.match(/thresholds\s*:\s*\{[\s\S]*?\n\s*\}/);
  if (thresholdsBlock) {
    const block = thresholdsBlock[0];
    const hasPercentile = /p\(\s*9[059]\s*\)/.test(block) || /p\(\s*99\.?\d*\s*\)/.test(block);
    const hasAvgOnly = /['"]avg\s*</.test(block) && !hasPercentile;
    if (hasAvgOnly) {
      addFinding('WARN', 'percentile-thresholds',
        'Thresholds use avg but not p95/p99. Average hides tail latency - add p(95) or p(99) thresholds.',
        findLine(/['"]avg\s*</));
    }
  }

  // CHECK 1b: Error rate threshold exists
  const hasErrorRate = /http_req_failed/.test(content);
  if (!hasErrorRate) {
    addFinding('ERROR', 'error-rate-threshold',
      'No http_req_failed threshold. Add \'http_req_failed\': [\'rate<0.01\'] to catch error spikes.');
  }

  // CHECK 1c: Checks threshold exists (if checks are used)
  const hasChecks = /\bcheck\s*\(/.test(content);
  const hasChecksThreshold = /['"]checks['"]\s*:/.test(content);
  if (hasChecks && !hasChecksThreshold) {
    addFinding('WARN', 'checks-threshold',
      'check() is used but no threshold on \'checks\' metric. Checks alone do NOT affect k6 exit code. Add \'checks\': [\'rate>0.99\'] to thresholds.',
      findLine(/\bcheck\s*\(/));
  }
}

// ─── CHECK 2: No hardcoded URLs ──────────────────────────────────────────────
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  // Skip comments and import lines
  if (/^\s*\/\//.test(line) || /^\s*\*/.test(line) || /^\s*import\s/.test(line)) continue;
  // Skip lines that are defining __ENV or using template literals with __ENV
  if (/__ENV/.test(line)) continue;

  const hardcodedUrl = line.match(/['"`](https?:\/\/[^'"`\s$]+)['"`]/);
  if (hardcodedUrl && isInDefaultFunction(i)) {
    addFinding('ERROR', 'hardcoded-url',
      `Hardcoded URL found: ${hardcodedUrl[1]}. Use __ENV.BASE_URL for portability.`,
      i + 1);
  }
}

// ─── CHECK 3: Uses __ENV for base URL ────────────────────────────────────────
const usesEnvBaseUrl = /__ENV\s*\.\s*BASE_URL/.test(content) || /__ENV\s*\[\s*['"]BASE_URL/.test(content);
const usesAnyEnvUrl = /__ENV/.test(content);
if (!usesEnvBaseUrl && !usesAnyEnvUrl) {
  addFinding('WARN', 'env-base-url',
    'No __ENV usage detected. Parameterize the target URL with __ENV.BASE_URL for portability across environments.');
}

// ─── CHECK 4: Think time present ─────────────────────────────────────────────
const hasSleep = /\bsleep\s*\(/.test(content);
const hasRandomSleep = /randomIntBetween|Math\.random/.test(content);
if (!hasSleep) {
  addFinding('WARN', 'think-time',
    'No sleep() call found. Add think time between requests to model real user behavior. Use sleep(randomIntBetween(1, 3)).');
} else if (!hasRandomSleep) {
  addFinding('INFO', 'randomized-think-time',
    'sleep() found but no randomization detected. Consider sleep(randomIntBetween(1, 3)) to prevent request synchronization.',
    findLine(/\bsleep\s*\(/));
}

// ─── CHECK 5: No console.log in hot path ─────────────────────────────────────
for (let i = 0; i < lines.length; i++) {
  if (/console\.(log|info|debug)\s*\(/.test(lines[i]) && isInDefaultFunction(i)) {
    addFinding('WARN', 'console-in-hotpath',
      'console.log/info/debug in default function. This serializes output and distorts timing. Use console.warn/error for failures only, or use custom metrics.',
      i + 1);
  }
}

// ─── CHECK 6: Scenarios defined ──────────────────────────────────────────────
const hasScenarios = /scenarios\s*:\s*\{/.test(content);
const hasExecutor = /executor\s*:/.test(content);
if (!hasScenarios && !hasExecutor) {
  addFinding('INFO', 'scenarios-defined',
    'No scenarios defined. Consider using named scenarios with explicit executors for clearer intent and per-scenario thresholds.');
}

// ─── CHECK 7: Arrival-rate executor recommended ──────────────────────────────
if (hasExecutor) {
  const usesArrivalRate = /constant-arrival-rate|ramping-arrival-rate/.test(content);
  const usesVuBased = /constant-vus|ramping-vus|shared-iterations|per-vu-iterations/.test(content);
  if (usesVuBased && !usesArrivalRate) {
    addFinding('INFO', 'arrival-rate-executor',
      'Using VU-based executor. For load testing, constant-arrival-rate is recommended - it decouples request rate from response time and avoids coordinated omission.',
      findLine(/executor\s*:/));
  }
}

// ─── CHECK 8: Has check() calls ─────────────────────────────────────────────
const hasCheckCalls = /\bcheck\s*\(/.test(content);
if (!hasCheckCalls) {
  addFinding('WARN', 'has-checks',
    'No check() calls found. Checks validate correctness (status codes, response shape). Without them, you only know the server responded, not that it responded correctly.');
}

// ─── CHECK 9: Descriptive scenario names ─────────────────────────────────────
const scenarioNames = content.match(/['"]?(\w+)['"]?\s*:\s*\{[^}]*executor/g);
if (scenarioNames) {
  for (const match of scenarioNames) {
    const name = match.match(/['"]?(\w+)['"]?\s*:/)?.[1];
    if (name && /^(test|scenario|default|main|s\d+)$/i.test(name)) {
      addFinding('INFO', 'descriptive-scenario-name',
        `Scenario name '${name}' is generic. Use descriptive names like 'browse_catalog' or 'checkout_flow' so reviewers know what is measured.`);
    }
  }
}

// ─── CHECK 10: setup() function exists ───────────────────────────────────────
const hasSetup = /export\s+function\s+setup/.test(content);
if (!hasSetup) {
  addFinding('INFO', 'setup-function',
    'No setup() function. If your test needs authentication or seed data, do it in setup() to keep it outside the measurement window.');
}

// ─── OUTPUT ──────────────────────────────────────────────────────────────────

const errors = findings.filter(f => f.severity === 'ERROR');
const warnings = findings.filter(f => f.severity === 'WARN');
const infos = findings.filter(f => f.severity === 'INFO');

if (jsonOutput) {
  console.log(JSON.stringify({
    file: filePath,
    summary: {
      errors: errors.length,
      warnings: warnings.length,
      info: infos.length,
      passed: errors.length === 0,
    },
    findings,
  }, null, 2));
} else {
  const fileName = path.basename(filePath);
  console.log(`\n  k6 Test Validator: ${fileName}`);
  console.log('  ' + '='.repeat(50));

  if (findings.length === 0) {
    console.log('\n  All checks passed.\n');
  } else {
    for (const f of findings) {
      const icon = f.severity === 'ERROR' ? 'x' : f.severity === 'WARN' ? '!' : 'i';
      const lineInfo = f.line ? ` (line ${f.line})` : '';
      console.log(`\n  [${icon}] ${f.severity}: ${f.check}${lineInfo}`);
      console.log(`      ${f.message}`);
    }
    console.log('\n  ' + '-'.repeat(50));
    console.log(`  ${errors.length} error(s), ${warnings.length} warning(s), ${infos.length} info`);

    if (errors.length > 0) {
      console.log('\n  Fix all ERRORs before merging.\n');
    } else {
      console.log('\n  No blocking issues. Review warnings.\n');
    }
  }
}

process.exit(errors.length > 0 ? 1 : 0);

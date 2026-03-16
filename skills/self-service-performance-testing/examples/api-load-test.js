/**
 * k6 Load Test: API Endpoint
 *
 * Scenario: Users requesting project data from a REST API.
 * Tests a single endpoint under steady-state load to establish
 * performance baselines and detect regressions.
 *
 * Run:
 *   k6 run --env BASE_URL=https://perf.example.com \
 *           --env PRIVATE_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx \
 *           examples/api-load-test.js
 *
 * Validate first:
 *   node scripts/validate-perf-test.js examples/api-load-test.js
 */

import http from 'k6/http';
import exec from 'k6/execution';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ─── Test Data ───────────────────────────────────────────────────────────────
// SharedArray loads data once and shares read-only across all VUs.
// This avoids duplicating memory per VU for large datasets.
const projectIds = new SharedArray('projects', function () {
  // Replace with your actual test data file or inline array
  return [1, 2, 5, 10, 42, 100, 250, 500, 1000, 2500];
});

// ─── Options ─────────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    get_project_details: {
      // constant-arrival-rate: maintains steady RPS regardless of response time.
      // This is the recommended executor for load testing - it decouples
      // throughput from latency, avoiding coordinated omission.
      executor: 'constant-arrival-rate',
      rate: 30,                // 30 requests per second
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 10,     // Start with 10 VUs
      maxVUs: 50,              // Scale up if system slows down
    },
  },

  thresholds: {
    // Per-scenario thresholds - these are your quality gates.
    // k6 exits non-zero if any threshold fails (CI-friendly).
    'http_req_duration{scenario:get_project_details}': [
      'p(95)<500',   // 95th percentile under 500ms
      'p(99)<1000',  // 99th percentile under 1s
    ],
    'http_req_failed': ['rate<0.01'],   // <1% error rate
    'checks': ['rate>0.99'],            // >99% of checks must pass
  },
};

// ─── Setup: runs once before all VUs ─────────────────────────────────────────
// Use a pre-generated Personal Access Token (PAT) for authentication.
// Pass it via __ENV.PRIVATE_TOKEN - never hardcode credentials in test files.
// The returned object is passed to the default function and teardown.
export function setup() {
  if (!__ENV.PRIVATE_TOKEN) {
    exec.test.abort('PRIVATE_TOKEN environment variable is required.');
  }

  return { token: __ENV.PRIVATE_TOKEN };
}

// ─── Default Function: runs per iteration ────────────────────────────────────
// This reads like a user story: pick a project, fetch its details, verify.
export default function (data) {
  const projectId = projectIds[Math.floor(Math.random() * projectIds.length)];

  const res = http.get(
    `${__ENV.BASE_URL}/api/v4/projects/${projectId}`,
    {
      headers: { 'PRIVATE-TOKEN': data.token },
      tags: { name: 'get-project-details' },  // Tag for filtering in results
    }
  );

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has project name': (r) => r.json('name') !== undefined,
    'has project id': (r) => r.json('id') === projectId,
  });

  // Randomized think time models real user pauses between actions.
  // Fixed sleep(1) causes all VUs to fire simultaneously - avoid it.
  sleep(randomIntBetween(1, 3));
}

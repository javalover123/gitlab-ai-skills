#!/usr/bin/env bash
# Run promptfoo LLM evals for skills that ship a tests/eval.yaml.
#
# Evals are behavioural tests: they feed a skill's SKILL.md to a model along
# with a task, and assert on the output (structural `contains` checks plus an
# `llm-rubric` quality score). They complement the deterministic checks in
# scripts/ — those verify a skill is well-formed; evals verify it actually
# steers a model the way it claims to.
#
# Requires an ANTHROPIC_API_KEY (the eval providers call the Anthropic API).
# Without it the script exits 0 with a skip notice, so CI stays green until the
# key is configured as a project CI/CD variable.
#
# Usage:
#   scripts/run_evals.sh                 # run every skill that has tests/eval.yaml
#   scripts/run_evals.sh commit-messages # run one skill's eval
#   scripts/run_evals.sh a b c           # run several by name
#
# Requires: node + npx (promptfoo is run via npx).

set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY not set — skipping LLM evals."
  echo "Set it as a CI/CD variable (or export it locally) to enable eval runs."
  exit 0
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx not found on PATH (need Node.js to run promptfoo)." >&2
  exit 1
fi

# Prefer a locally-installed promptfoo (from devDependencies) for
# reproducibility; fall back to a pinned npx download when it isn't installed.
if [ -x "node_modules/.bin/promptfoo" ]; then
  promptfoo() { node_modules/.bin/promptfoo "$@"; }
else
  promptfoo() { npx --yes promptfoo@0.117.0 "$@"; }
fi

# Resolve which eval configs to run.
configs=()
if [ "$#" -gt 0 ]; then
  for name in "$@"; do
    cfg="skills/${name}/tests/eval.yaml"
    if [ -f "$cfg" ]; then
      configs+=("$cfg")
    else
      echo "WARNING: no eval config for '${name}' (${cfg} not found)" >&2
    fi
  done
else
  # compgen -G glob-expands safely; a plain [ -f glob* ] never matches.
  while IFS= read -r cfg; do
    configs+=("$cfg")
  done < <(compgen -G "skills/*/tests/eval.yaml" || true)
fi

if [ "${#configs[@]}" -eq 0 ]; then
  echo "No skill eval configs found (skills/*/tests/eval.yaml)."
  exit 0
fi

echo "Running ${#configs[@]} skill eval(s):"
printf '  %s\n' "${configs[@]}"
echo

failed=0
for cfg in "${configs[@]}"; do
  echo "=== promptfoo eval -c ${cfg} ==="
  if ! promptfoo eval -c "$cfg"; then
    echo "FAIL: eval failed for ${cfg}" >&2
    failed=1
  fi
  echo
done

if [ "$failed" -eq 1 ]; then
  echo "One or more evals failed." >&2
  exit 1
fi
echo "All evals passed."

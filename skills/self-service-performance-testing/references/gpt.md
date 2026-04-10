# GPT — GitLab Performance Tool

**Repo:** https://gitlab.com/gitlab-org/quality/performance
**Quick start:** https://gitlab.com/gitlab-org/quality/performance/-/blob/main/docs/quick_start.md
**Existing tests:** https://gitlab.com/gitlab-org/quality/performance/-/tree/main/k6/tests

GPT is a Ruby orchestration layer around k6 with pre-built test suites for
GitLab API, web, and Git endpoints. It includes opinionated data generators,
version-aware thresholds, automatic scoring, and failure evaluation reports.

## How It Works

GPT runs externally via Docker. The engineer doesn't add test files to their
project — they configure and run tests from the GPT repo.

1. **Create admin user** on the target GitLab instance with API PAT (all
   permissions). Must be able to create groups.
2. **Configure environment** — JSON file with instance URL, user, Gitaly
   storage nodes
3. **Generate test data** — `docker run gitlab/gpt-data-generator` creates
   horizontal data (1000 subgroups x 10 projects) and vertical data (large
   projects with issues, MRs, pipelines, commits)
4. **Run tests** — `docker run gitlab/gitlab-performance-tool --environment
   <env>.json --options <load>.json`
5. **Interpret results** — Overall Results Score (target >90%), per-test
   RPS/TTFB/success rate, failure evaluation report with recommendations

## Test Structure (k6 Under the Hood)

GPT tests are k6 scripts with GPT-specific metadata and helper modules:

- `k6/tests/api/` — REST API endpoint tests (100% of target RPS)
- `k6/tests/web/` — Web page response tests (10% of target RPS)
- `k6/tests/git/` — Git operation tests (10% of target RPS)
- `k6/tests/scenarios/` — Multi-step user journeys (excluded by default,
  require `--unsafe` flag as they create/delete data)

Each test file includes metadata comments that GPT uses for filtering:

```javascript
/*
@endpoint: `GET /api/v4/groups`
@description: Tests the groups list API endpoint
@gpt_data_version: 1
@flags: unsafe
@stressed_components: Rails, Postgres
@gitlab_version: 15.0
*/
import { logError, getRpsThresholds, getTtfbThreshold } from "../../lib/gpt_k6_modules.js"

// Version-aware thresholds — GPT selects based on target GitLab version
export let thresholds = {
  'rps': { '16.10.0': 0.6, 'latest': 0.6 },
  'ttfb': { '16.10.0': 2000, 'latest': 3000 },
};
```

**Helper modules:**
- `gpt_k6_modules.js` — `getRpsThresholds()`, `getTtfbThreshold()`,
  `getLargeProjects()`, `selectRandom()`, `logError()`, `adjustRps()`
- `gpt_git_functions.js` — Git protocol operations (clone, pull, push)
- `gpt_scenario_functions.js` — Group/project CRUD for scenario tests
- `gpt_data_helper_functions.js` — URL and pipeline helpers

## Scoring System

Per-test: `score = min((rps_achieved / rps_target) * success_rate, 100)`
Overall: average of per-test scores. Target: **>90%**.

Failed tests automatically retry once. Results output in JSON, CSV, TXT,
and a Markdown failure evaluation report with debugging recommendations.

## Load Options

Predefined profiles mapped to GitLab reference architectures:

| Users | Target RPS | Option file |
|---|---|---|
| 1,000 | 20 | `60s_20rps.json` |
| 2,000 | 40 | `60s_40rps.json` |
| 5,000 | 100 | `60s_100rps.json` |
| 10,000 | 200 | `60s_200rps.json` |
| 25,000 | 500 | `60s_500rps.json` |
| 50,000 | 1000 | `60s_1000rps.json` |

Each option file defines ramp-up, sustained, and ramp-down stages.

## Running GPT

```bash
# Docker (recommended)
docker run -it \
  -e ACCESS_TOKEN=<your-pat> \
  -v $(pwd)/config:/config \
  -v $(pwd)/results:/results \
  gitlab/gitlab-performance-tool \
  --environment 10k.json \
  --options 60s_200rps.json \
  --tests api

# Local (requires Ruby + k6)
./bin/run-k6 --environment 10k.json --options 60s_200rps.json --tests api
```

**Key flags:** `--tests api|web|git|scenarios`, `--unsafe` (enable
POST/PUT/DELETE tests), `--quarantined`, `--experimental`,
`--excludes <pattern>`.

**Key env var:** `ACCESS_TOKEN` (admin PAT with all permissions).

## When to Use GPT

- Validating GitLab reference architectures
- Load testing API/web/git endpoints under realistic conditions
- Establishing performance baselines for backend changes
- Scheduled load tests (nightly/weekly)

## When NOT to Use GPT

- Quick MR-level smoke test → use CPT or custom k6 in CI
- Frontend page load → use Sitespeed Runway
- Need a test embedded in the project's repo → custom k6

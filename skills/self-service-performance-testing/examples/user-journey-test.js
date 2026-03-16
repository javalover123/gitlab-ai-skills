/**
 * k6 Load Test: User Journey (Multi-Step)
 *
 * Scenario: A user logs in, browses projects, opens a merge request,
 * and posts a comment. Each step is tagged and grouped for independent
 * threshold tracking.
 *
 * Run:
 *   k6 run --env BASE_URL=https://perf.example.com \
 *           --env PRIVATE_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx \
 *           examples/user-journey-test.js
 *
 * Validate first:
 *   node scripts/validate-perf-test.js examples/user-journey-test.js
 */

import http from 'k6/http';
import exec from 'k6/execution';
import { check, group, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ─── Test Data ───────────────────────────────────────────────────────────────
// IMPORTANT: These IDs must point to a dedicated test project in your perf
// environment. Never target real projects - this test creates comments on MRs
// which would pollute real review threads.
const testData = new SharedArray('mr-data', function () {
  // Each entry represents a project + MR combination to test against.
  // Use varied data to exercise the application, not the cache.
  return [
    { projectId: 1, mrIid: 10 },
    { projectId: 1, mrIid: 25 },
    { projectId: 5, mrIid: 3 },
    { projectId: 42, mrIid: 7 },
    { projectId: 100, mrIid: 1 },
  ];
});

// ─── Options ─────────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    mr_review_journey: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      stages: [
        { target: 5, duration: '1m' },   // Warmup at 5 RPS
        { target: 20, duration: '3m' },   // Ramp to 20 RPS
        { target: 20, duration: '5m' },   // Hold at 20 RPS
        { target: 0, duration: '1m' },    // Ramp down
      ],
      preAllocatedVUs: 20,
      maxVUs: 100,
    },
  },

  thresholds: {
    // Overall thresholds
    'http_req_failed': ['rate<0.01'],
    'checks': ['rate>0.99'],

    // Per-step thresholds using tags - different SLOs for different operations.
    // Browse is expected to be fast; posting a comment can be slower.
    'http_req_duration{step:browse_projects}': ['p(95)<300'],
    'http_req_duration{step:open_mr}': ['p(95)<500'],
    'http_req_duration{step:post_comment}': ['p(95)<800'],

    // Group duration tracks the full journey end-to-end
    'group_duration{group:::MR Review Journey}': ['p(95)<3000'],
  },
};

// ─── Setup ───────────────────────────────────────────────────────────────────
// Use a pre-generated Personal Access Token (PAT) for authentication.
// Pass via __ENV.PRIVATE_TOKEN - never hardcode credentials in test files.
export function setup() {
  if (!__ENV.PRIVATE_TOKEN) {
    exec.test.abort('PRIVATE_TOKEN environment variable is required.');
  }

  return { token: __ENV.PRIVATE_TOKEN };
}

// ─── Default Function ────────────────────────────────────────────────────────
// Reads like a user story: browse → open MR → comment.
export default function (data) {
  const entry = testData[Math.floor(Math.random() * testData.length)];
  const headers = {
    'PRIVATE-TOKEN': data.token,
    'Content-Type': 'application/json',
  };

  group('MR Review Journey', function () {
    // Step 1: Browse projects
    const projectsRes = http.get(
      `${__ENV.BASE_URL}/api/v4/projects?per_page=20`,
      { headers, tags: { step: 'browse_projects' } }
    );
    check(projectsRes, {
      'projects: status 200': (r) => r.status === 200,
      'projects: returns array': (r) => Array.isArray(r.json()),
    });

    sleep(randomIntBetween(1, 2));

    // Step 2: Open merge request
    const mrRes = http.get(
      `${__ENV.BASE_URL}/api/v4/projects/${entry.projectId}/merge_requests/${entry.mrIid}`,
      { headers, tags: { step: 'open_mr' } }
    );
    check(mrRes, {
      'mr: status 200': (r) => r.status === 200,
      'mr: has title': (r) => r.json('title') !== undefined,
    });

    sleep(randomIntBetween(2, 5)); // User reads the MR

    // Step 3: Post a comment
    // NOTE: This creates notes that are not cleaned up. For repeated runs,
    // periodically delete test notes or use a disposable test project.
    const commentRes = http.post(
      `${__ENV.BASE_URL}/api/v4/projects/${entry.projectId}/merge_requests/${entry.mrIid}/notes`,
      JSON.stringify({ body: 'Performance test comment - safe to ignore.' }),
      { headers, tags: { step: 'post_comment' } }
    );
    check(commentRes, {
      'comment: status 201': (r) => r.status === 201,
    });

    sleep(randomIntBetween(1, 3));
  });
}

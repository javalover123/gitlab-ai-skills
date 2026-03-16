# k6 Patterns and Best Practices

Deep reference for k6-specific decisions. k6 is the engine behind both GPT
(GitLab Performance Tool) and CPT. Whether you're writing custom tests or
understanding GPT's pre-built suites, these patterns apply. For general k6
API documentation, refer to the k6 docs directly.

## Open vs Closed Model

This is the most important concept for accurate load testing.

**Open model** (arrival-rate executors): New requests arrive at a fixed rate
regardless of response time. If the server slows down, more VUs are spawned to
maintain throughput. This models real-world traffic where users don't wait for
each other.

**Closed model** (VU-based executors): A fixed number of VUs loop. If the
server slows down, throughput drops proportionally. This hides the problem -
a slow server looks like it has less load.

**Use arrival-rate for load testing.** VU-based executors are fine for smoke
tests and scripted journeys where you control iteration count.

When using `constant-arrival-rate`, always set `preAllocatedVUs` and `maxVUs`:

```javascript
scenarios: {
  api_load: {
    executor: 'constant-arrival-rate',
    rate: 50,
    timeUnit: '1s',
    duration: '5m',
    preAllocatedVUs: 20,   // Pre-warm this many
    maxVUs: 100,           // Scale up if system slows
  },
},
```

Monitor the `dropped_iterations` metric - if it's non-zero, you need more
`maxVUs` than the system can support at the target rate.

## Threshold Gotchas

### Per-scenario thresholds using tags

```javascript
thresholds: {
  'http_req_duration{scenario:browse}': ['p(95)<300'],
  'http_req_duration{scenario:checkout}': ['p(95)<800'],
}
```

### Abort on failure

Use `abortOnFail` for stress tests to prevent overwhelming the SUT. Delay
evaluation to collect meaningful samples first:

```javascript
thresholds: {
  'http_req_duration': [
    { threshold: 'p(99)<2000', abortOnFail: true, delayAbortEval: '30s' },
  ],
}
```

### Trap: duplicate keys

JavaScript object keys must be unique. This silently drops the first:

```javascript
// BAD: second 'http_req_duration' overwrites the first
thresholds: {
  'http_req_duration': ['p(95)<500'],
  'http_req_duration': ['p(99)<1000'],  // Only this one applies!
}

// GOOD: array of conditions on one key
thresholds: {
  'http_req_duration': ['p(95)<500', 'p(99)<1000'],
}
```

### Trap: checks without thresholds

`check()` failures do NOT affect the k6 exit code. They are informational
unless you create a threshold:

```javascript
thresholds: {
  'checks': ['rate>0.99'],    // Now check failures cause non-zero exit
}
```

## Lifecycle and VU Isolation

```
1. init code     - runs once per VU, loads modules and data
2. setup()       - runs once total, returns data for default + teardown
3. default()     - runs per iteration per VU (the measured code)
4. teardown()    - runs once total after all iterations complete
```

**Critical gotchas:**

- Each VU is an isolated JavaScript runtime. Module-level `let/var` variables
  are NOT shared between VUs.
- `setup()` return value is serialized as JSON. Only JSON-serializable data
  survives into `default()` and `teardown()`.
- `teardown()` cannot access module-level state accumulated during VU
  iterations. Design cleanup into the scenario itself (create-use-delete per
  iteration) rather than accumulating state.
- `open()` only works in init context (step 1), not inside `default()`.

## Multi-Scenario Configuration

Use `exec` to point scenarios at named exports, and `startTime` to stagger:

```javascript
scenarios: {
  browse_catalog: {
    executor: 'constant-arrival-rate',
    rate: 100, timeUnit: '1s', duration: '10m',
    preAllocatedVUs: 50, maxVUs: 200,
    exec: 'browseCatalog',
  },
  checkout_flow: {
    executor: 'constant-arrival-rate',
    rate: 10, timeUnit: '1s', duration: '10m',
    preAllocatedVUs: 5, maxVUs: 20,
    exec: 'checkoutFlow',
    startTime: '2m',
  },
},
```

## Authentication Patterns

### Pre-generated token (default)

Use a pre-generated PAT or API key via environment variable. Simplest and
most reliable:

```javascript
export function setup() {
  if (!__ENV.PRIVATE_TOKEN) {
    exec.test.abort('PRIVATE_TOKEN is required');
  }
  return { token: __ENV.PRIVATE_TOKEN };
}

export default function (data) {
  http.get(`${__ENV.BASE_URL}/api/resource`, {
    headers: { 'PRIVATE-TOKEN': data.token },
  });
}
```

### OAuth2 token exchange

When you need a short-lived token, exchange in `setup()`:

```javascript
export function setup() {
  const res = http.post(`${__ENV.BASE_URL}/oauth/token`, JSON.stringify({
    grant_type: 'password',
    username: __ENV.TEST_USER,
    password: __ENV.TEST_PASS,
  }), { headers: { 'Content-Type': 'application/json' } });

  return { token: res.json('access_token') };
}
```

### Per-VU auth (when tokens expire or are user-specific)

```javascript
const credentials = new SharedArray('creds', function () {
  return JSON.parse(open('./data/users.json'));
});

export default function () {
  const cred = credentials[__VU % credentials.length];
  // Auth and test...
}
```

## Rails / Go Context

k6 tests the system from outside - the backend language doesn't affect how
you write the test. But it affects what you test *for*:

### Ruby on Rails

- **N+1 queries**: Test endpoints that return collections (e.g., project list
  with associations). Use varied `per_page` values and check response times
  scale linearly, not exponentially.
- **Puma concurrency**: Set k6 VU count to exceed your Puma worker/thread
  count to reveal queuing and thread contention.
- **Sidekiq throughput**: Test API endpoints that enqueue background jobs. The
  API response time should remain fast even under load - if it degrades, the
  enqueueing path has contention.
- **ActiveRecord connection pool**: High concurrency can exhaust the connection
  pool. Test with VU counts exceeding `pool` size in `database.yml`.

### Go services

- **Goroutine leaks under load**: Sustained high-concurrency tests (stress
  profile) can reveal goroutine leaks that don't appear in unit tests.
- **Memory allocation patterns**: Go's GC pauses can cause tail latency spikes
  visible at p99. Use stress tests to surface these.

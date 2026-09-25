# Observability-driven debugging recipes

This reference is loaded on demand from the `bugfix` skill during Phase 2
(context gathering, log / trace rung) and Phase 4 (causal analysis). It
captures the recipes that turn logs and traces from a record into a
diagnostic instrument — span trees as causal evidence, structured fields
as queryable diagnostics, and `traceparent` propagation that follows a
single logical operation across services.

The goal of every recipe here's the same: turn an observed symptom into a
falsifiable hypothesis with a citation, so Phase 4's three-way diff
grounds in evidence rather than speculation.

Examples are in Rust (`tracing` + OpenTelemetry) and Python (`logging` /
`structlog` + OpenTelemetry). The patterns translate to most languages
with structured logging plus an OTLP exporter.

## Part 1 — Reading what's already there

Before reaching for new instrumentation, fully consume what the running
system already emits. Most bugs are diagnosable from existing spans and
fields if you ask the right questions.

### Filter to the relevant target / logger

**Rust (`tracing`):**

```bash
# Single component
RUST_LOG=app_dispatcher::handler=debug cargo run --bin app

# Multiple components with a default level
RUST_LOG=warn,app_dispatcher=debug,app_link=trace cargo run

# Everything in a crate
RUST_LOG=app_dispatcher=trace cargo run
```

**Python (`logging`):**

```python
# In code
import logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger("app.dispatcher").setLevel(logging.DEBUG)
logging.getLogger("app.link").setLevel(logging.DEBUG)
```

```bash
# Via env (with python-json-logger or structlog reading LOG_LEVEL)
LOG_LEVEL=DEBUG APP_DISPATCHER_LEVEL=DEBUG python -m app
```

For a captured JSON log file:

```bash
# Find all events for a target / logger
jq 'select(.target | startswith("app.dispatcher"))' logs.json

# Find events with a specific field value
jq 'select(.fields.task_id == "task-7f3a9c")' logs.json

# Pretty-print the span chain for a single trace
jq 'select(.span.trace_id == "abc123") | {ts: .timestamp, lvl: .level, msg: .fields.message, span: .span.name}' logs.json
```

### Read the span tree, not just the events

A span tree's causal evidence. An event inside span B inside span A means
"A called something that called B, which emitted this event." When you're
investigating, reconstruct that tree before drawing conclusions:

```bash
# Build a parent → child chain for a single trace
jq -r '
  select(.span.trace_id == "abc123")
  | "\(.timestamp) \(.span.parent_span_id // "ROOT") -> \(.span.span_id) \(.span.name) \(.fields.message // "")"
' logs.json | sort
```

Patterns to look for:

- **Spans that open but never close** → likely a missing cleanup
  (`Drop` / `__del__` / context manager `__exit__`), or a future or task
  dropped before completion. Classic source of silent-failure bugs.
- **Spans whose children are missing the expected siblings** → a code
  path was skipped (e.g., `task_dispatched` without a matching
  `task_completed` or `task_failed`).
- **Long gaps between sibling spans** → a synchronous wait, lock
  contention, or a missing async yield.
- **Spans firing in the wrong process** → trace propagation broke at some
  boundary; see Part 3.

### Live introspection for async runtimes

When the bug's "the system gets stuck" rather than "the system does the
wrong thing," runtime introspection tools beat log archaeology.

**Rust + tokio:**

```bash
# In Cargo.toml
# [dependencies]
# console-subscriber = "0.4"
# tokio = { version = "1", features = ["full", "tracing"] }
#
# In main:
# console_subscriber::init();

RUSTFLAGS="--cfg tokio_unstable" cargo install tokio-console
tokio-console
```

**Python + asyncio:**

```python
# Python 3.12+
import asyncio
asyncio.run(main(), debug=True)  # warns about slow callbacks, missing awaits

# Or attach an external profiler:
# py-spy dump --pid <pid>
# py-spy top --pid <pid>
```

Look for tasks idle for unexpectedly long (blocked on a channel that has
no sender), resources with rising contention counts, or tasks created but
never polled or awaited.

## Part 2 — Adding instrumentation during diagnosis

When existing telemetry doesn't answer the question, add targeted
instrumentation. Keep diagnostic value high and noise low.

### Function-level spans

**Rust:**

```rust
use tracing::instrument;

#[instrument(
    skip(self, payload),
    fields(
        task_id = %task_id,
        payload_len = payload.len(),
        peer = ?self.peer_id,
    ),
    err,
    ret(level = "trace"),
)]
async fn dispatch_task(
    &self,
    task_id: TaskId,
    payload: Vec<u8>,
) -> Result<DispatchAck, DispatchError> {
    // ...
}
```

Field syntax:

| Syntax            | Effect                                     |
|-------------------|--------------------------------------------|
| `task_id`         | Records via Debug                          |
| `task_id = %x`    | Records via Display                        |
| `task_id = ?x`    | Records via Debug (explicit)               |
| `task_id = x.id()`| Records the expression's result            |

**Python (using OpenTelemetry):**

```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

async def dispatch_task(self, task_id, payload):
    with tracer.start_as_current_span("dispatch_task") as span:
        span.set_attribute("task_id", str(task_id))
        span.set_attribute("payload_len", len(payload))
        span.set_attribute("peer", repr(self.peer_id))
        try:
            result = await self._do_dispatch(task_id, payload)
            return result
        except DispatchError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

### Recording fields after-the-fact

Sometimes the value isn't known when the span opens. Record it later:

**Rust:**

```rust
let span = tracing::info_span!("process_request", request_id = tracing::field::Empty);
let _enter = span.enter();
// ... derive request_id from input ...
span.record("request_id", &tracing::field::display(&request_id));
```

**Python:**

```python
with tracer.start_as_current_span("process_request") as span:
    # ... derive request_id from input ...
    span.set_attribute("request_id", str(request_id))
```

### Error tracking with span context

**Rust (`tracing-error` or `eyre`):**

```rust
// Cargo.toml
// tracing-error = "0.2"   OR   color-eyre = "0.6"

use tracing_error::{SpanTrace, ErrorLayer};

#[derive(Debug, thiserror::Error)]
#[error("dispatch failed for task {task_id}")]
pub struct DispatchError {
    pub task_id: TaskId,
    pub source: Box<dyn std::error::Error + Send + Sync>,
    pub span_trace: SpanTrace,
}

// In main:
tracing_subscriber::registry()
    .with(fmt::layer())
    .with(ErrorLayer::default())
    .init();
```

If your project already uses `eyre` / `color-eyre`, you get span traces
on errors for free — `color_eyre::install()` does the wiring.

**Python:**

```python
import structlog

logger = structlog.get_logger()

try:
    await dispatch(task_id)
except DispatchError as e:
    logger.error(
        "dispatch_failed",
        task_id=str(task_id),
        error_kind=type(e).__name__,
        error_detail=str(e),
        exc_info=True,
    )
    raise
```

### Diagnostic levels

| Level   | When to use                                               |
|---------|-----------------------------------------------------------|
| `error` | Unrecoverable; surfaces to operator dashboards            |
| `warn`  | Recoverable degradation; retried operations               |
| `info`  | One-per-request milestones; lifecycle events              |
| `debug` | Per-step inside a request; structured field captures      |
| `trace` | Per-line or per-loop-iteration; only enabled when chasing |
| (Python `notset` / `verbose` plugins extend the same shape) | |

In a bugfix session, default new instrumentation to `debug`. Promote to
`info` only the events that prove useful as permanent operator signals.
Delete the rest before committing.

## Part 3 — Cross-service tracing

A single logical operation can span several services. The trace must
follow.

### `traceparent` in your transport envelope

Every message envelope carries a W3C `traceparent` (and optional
`tracestate`) field. On the send side, inject the current context:

**Rust:**

```rust
use opentelemetry::global;
use opentelemetry::trace::TraceContextExt;
use opentelemetry_http::HeaderInjector;
use tracing_opentelemetry::OpenTelemetrySpanExt;

fn build_envelope(payload: Vec<u8>) -> Envelope {
    let mut headers = HashMap::new();
    let cx = tracing::Span::current().context();
    global::get_text_map_propagator(|p| {
        p.inject_context(&cx, &mut HeaderInjector(&mut headers));
    });
    Envelope {
        traceparent: headers.get("traceparent").cloned(),
        tracestate: headers.get("tracestate").cloned(),
        payload,
    }
}
```

**Python:**

```python
from opentelemetry import trace
from opentelemetry.propagate import inject

def build_envelope(payload: bytes) -> Envelope:
    headers = {}
    inject(headers)
    return Envelope(
        traceparent=headers.get("traceparent"),
        tracestate=headers.get("tracestate"),
        payload=payload,
    )
```

On the receive side, extract and continue:

**Rust:**

```rust
use opentelemetry_http::HeaderExtractor;
use tracing_opentelemetry::OpenTelemetrySpanExt;

fn handle_envelope(env: Envelope) {
    let mut headers = HashMap::new();
    if let Some(tp) = env.traceparent { headers.insert("traceparent".into(), tp); }
    if let Some(ts) = env.tracestate { headers.insert("tracestate".into(), ts); }

    let parent_cx = global::get_text_map_propagator(|p| {
        p.extract(&HeaderExtractor(&headers))
    });
    let span = tracing::info_span!("handle_envelope");
    span.set_parent(parent_cx);
    let _enter = span.enter();
    // ... process ...
}
```

**Python:**

```python
from opentelemetry.propagate import extract

def handle_envelope(env: Envelope) -> None:
    headers = {}
    if env.traceparent: headers["traceparent"] = env.traceparent
    if env.tracestate: headers["tracestate"] = env.tracestate

    ctx = extract(headers)
    with tracer.start_as_current_span("handle_envelope", context=ctx):
        # ... process ...
        ...
```

### Following a single operation across services

When a bug spans services ("service A dispatched but service B never
acknowledged"), the workflow's:

1. Capture the `trace_id` from the symptom (an error log, a metric
   exemplar, or a user-reported request ID).
2. Find every span / event with that `trace_id` across every service's
   log output.
3. Reconstruct the parent → child tree across processes.

```bash
trace_id="abc123def456"
for log in logs/service-*.json; do
    jq --arg tid "$trace_id" \
       'select(.span.trace_id == $tid)
        | {ts: .timestamp, service: input_filename, span: .span.name, msg: .fields.message}' \
       "$log"
done | jq -s 'sort_by(.ts)'
```

A proper distributed-tracing backend (Jaeger, Tempo, Honeycomb, Datadog
APM, etc.) will render this tree for you. Prefer the backend over manual
`jq` when one's available — your manual reconstruction's a last resort
for when the backend's not in scope.

## Part 4 — Connecting metrics to traces with exemplars

When a metric anomaly (latency spike, error spike) is the entry point to
investigation, OpenTelemetry exemplars link the metric data point back to
a specific trace.

**Rust:**

```rust
// Cargo.toml
// opentelemetry = { version = "0.27", features = ["metrics"] }
// opentelemetry_sdk = { version = "0.27", features = ["metrics", "rt-tokio"] }

use opentelemetry::metrics::Counter;
use opentelemetry::KeyValue;

let counter: Counter<u64> = meter.u64_counter("dispatch_failures").init();

// Inside a span (so the exemplar captures the trace_id):
counter.add(1, &[KeyValue::new("reason", "timeout")]);
```

**Python:**

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
dispatch_failures = meter.create_counter("dispatch_failures")

# Inside a span context (so the exemplar captures the trace_id):
dispatch_failures.add(1, {"reason": "timeout"})
```

When you're investigating:

1. See a spike in `dispatch_failures{reason="timeout"}` at 14:32 UTC.
2. Pull exemplars for that data point → get a representative `trace_id`.
3. Follow Part 3 to reconstruct the trace across services.
4. Use that trace as the concrete reproducer seed.

To extract an exemplar from an OTLP export, use the backend's API or
`jq`:

```bash
# Find exemplars from an OTLP JSON dump
jq '.resourceMetrics[].scopeMetrics[].metrics[]
    | select(.name == "dispatch_failures")
    | .sum.dataPoints[].exemplars[]
    | {time: .timeUnixNano, traceId: .traceId, value: .asInt}' \
    metrics.json
```

## Part 5 — The log → trace → reproducer pipeline

This is the canonical Phase 2 → Phase 3 path when the symptom appears in
logs:

```
1. SYMPTOM in logs
   ↓ (search by field: task_id, peer_id, error variant)
2. EVENTS bracketing the symptom
   ↓ (extract trace_id from any matching event)
3. SPAN TREE for that trace_id
   ↓ (identify the missing or wrong span — that's the divergence line)
4. CALLSITE — file:line of the wrong or missing span
   ↓ (Read the surrounding code)
5. HYPOTHESIS (Phase 4)
   ↓
6. REPRODUCER input that recreates the same span tree shape
   ↓ (this is the Phase 3 test)
7. FAILING TEST with verbatim error captured
```

If you can't get from step 1 to step 4 with existing instrumentation,
adding instrumentation to bridge the gap's **diagnostic work**, not fix
work — keep it in a separate commit, and decide at Phase 7 whether each
added span / event becomes permanent (operator-useful) or gets removed
(noise).

## Part 6 — Sampling: don't let it hide your bug

If the system uses head-sampling (every Nth trace gets exported), rare
bugs are the most likely to be dropped — that's the whole point of
sampling, and it's exactly the wrong thing for diagnosis.

When you're chasing a rare bug:

- **Disable sampling for the affected service** during the diagnostic
  window. For OpenTelemetry, set the sampler to `AlwaysOnSampler`
  temporarily.
- **Use tail-sampling** if available — exports traces *after* they
  complete, based on rules like "trace had an error" or "trace took
  > 5s." Both Jaeger and Tempo support this via the OTel Collector's
  tail-sampling processor.
- **Use exemplars** (Part 4) — even with head-sampling, exemplars on
  error counters often capture the rare trace.

```yaml
# Example OTel Collector tail-sampling rule
processors:
  tail_sampling:
    decision_wait: 30s
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow
        type: latency
        latency: {threshold_ms: 5000}
```

Document the sampling change in your phase log so it doesn't get left in
production by mistake.

## Part 7 — Tracing in tests

Phase 3 reproducers sometimes need to assert on emitted spans (e.g., "the
fix emits a `task_failed` event"). Set up a test subscriber that captures
spans for inspection.

**Rust:**

```rust
use tracing_subscriber::fmt::TestWriter;
use tracing_test::traced_test;

#[traced_test]
#[tokio::test]
async fn disconnect_emits_task_failed_event() {
    let dispatcher = Dispatcher::new();
    dispatcher.simulate_disconnect().await;

    // tracing-test captures all emitted events
    assert!(logs_contain("task_failed"));
    assert!(logs_contain("reason=worker_disconnected"));
}
```

For finer-grained assertions, use the `tracing-subscriber` test layer:

```rust
use tracing::subscriber::with_default;
use tracing_subscriber::fmt::TestWriter;

#[tokio::test]
async fn task_failed_carries_required_fields() {
    let buffer = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
    let subscriber = tracing_subscriber::fmt()
        .with_writer(TestWriter::default())
        .json()
        .finish();
    with_default(subscriber, || {
        // ... your test ...
    });
    // Inspect buffer for emitted JSON events
}
```

**Python (`pytest`):**

```python
def test_disconnect_emits_task_failed_event(caplog):
    with caplog.at_level(logging.DEBUG, logger="app.dispatcher"):
        dispatcher = Dispatcher()
        dispatcher.simulate_disconnect()

    failed = [r for r in caplog.records if r.message.startswith("task_failed")]
    assert len(failed) == 1
    assert failed[0].reason == "worker_disconnected"
```

For structured logs (`structlog`), use `structlog.testing.LogCapture`:

```python
import structlog
from structlog.testing import LogCapture

def test_disconnect_logs_task_failed():
    cap = LogCapture()
    structlog.configure(processors=[cap])

    Dispatcher().simulate_disconnect()

    entries = [e for e in cap.entries if e["event"] == "task_failed"]
    assert len(entries) == 1
    assert entries[0]["reason"] == "worker_disconnected"
```

For OpenTelemetry span assertions:

```python
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

def test_dispatch_emits_span():
    exporter = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))

    dispatcher = Dispatcher()
    dispatcher.dispatch(Task("hello"))

    spans = exporter.get_finished_spans()
    dispatch_spans = [s for s in spans if s.name == "dispatch_task"]
    assert len(dispatch_spans) == 1
    assert dispatch_spans[0].attributes["task_id"] is not None
```

## Part 8 — Diagnostic-instrumentation hygiene

Forbidden during a bugfix session:

- Removing existing spans or events because they're "noisy." File the
  signal-to-noise concern as out-of-scope and continue.
- Lowering an existing span's level to silence it.
- Adding `println!` / `print` for diagnosis. Use structured `debug!` /
  `logger.debug()` with fields.
- Committing trace-level instrumentation that fires per-loop-iteration
  in a hot path. Either guard it (`if tracing::enabled!(Level::TRACE)`)
  or remove it before commit.

Required at end of Phase 6:

- Every span or event added during diagnosis is either (a) promoted to
  permanent with a justification ("this signal's operator-actionable") or
  (b) removed.
- Any new permanent span has structured fields, not interpolated strings
  (`task_id = %id`, not `format!("task {id}")`).
- Default log levels in `main` still produce useful output without
  flooding stderr at `info`.
- If sampling was changed for diagnosis, the change is reverted or
  documented as a permanent decision (which itself needs an ADR — see
  Phase 7a).

## Part 9 — Span and event conventions

**Span names:** `<noun>_<verb>` or `<verb>_<noun>`, lowercase with
underscores (`task_dispatch`, `handle_disconnect`, `worker_register`).

**Event names inside spans:** past-tense verb describing what just
happened (`task_dispatched`, `worker_disconnected`, `result_persisted`).

**Required fields on cross-process spans:**

- `trace_id` (auto from OpenTelemetry context)
- `span_id` (auto)
- Service or instance identifier (`service.name`, `instance_id`)
- The primary domain identifier (`task_id`, `request_id`)

**Errors:** emit an `error!` event with `error.kind` and `error.detail`
fields before returning the error, so logs aggregate by kind without
parsing message strings.

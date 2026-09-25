# Four-layer test pyramid

This reference is loaded on demand from the `bugfix` skill during Phase 3
(reproducer) when you're deciding which test layer a new reproducer
belongs in, and during Phase 6 (verification) when you're picking which
suites to run.

It exists because the most common test-quality regression in agentic bug
fixes is **layer drift** — putting an integration test where a unit test
would've caught the bug, or vice versa. That hides the real diagnosis
behind setup complexity, and sometimes skips classes of bugs entirely.

The four layers aren't arbitrary tiers. Each is defined by what it can and
can't observe, and each catches a class of bugs the others can't. Choose
by what the bug is, not by what feels comfortable to write.

## The four layers at a glance

| Layer | Name             | What it observes                          | What it can't                          | Speed |
|-------|------------------|-------------------------------------------|----------------------------------------|-------|
| L1    | Unit             | Pure functions, in-process state          | Module boundaries, I/O, async runtimes | <1ms  |
| L2    | Component        | Module boundaries, trait wiring, serde    | Real transport, persistent storage     | <100ms|
| L3    | BDD / workflow   | Multi-service flows, real I/O, time       | Adversarial input space, race classes  | <10s  |
| L4    | Invariant / prop | Universal properties over generated input | Specific scenario reproduction         | <60s  |

You'll also see Layer 0 — mutation testing — discussed in the sibling
reference [reproducer-and-mutation.md](reproducer-and-mutation.md). It's a
meta-layer that asks "does my test suite actually constrain the fix?"
rather than "does my code do the right thing?"

## Layer 1 — Unit

**What it is:** A pure function or data transformation tested in
isolation. No I/O, no async runtime (or a fully synchronous one), no
fakes more elaborate than a struct literal.

**When the bug belongs here:**

- Wrong arithmetic, wrong comparison, wrong boolean logic.
- Wrong enum match arm or default branch.
- Serialisation / deserialisation of a single value (not a protocol).
- Pure error construction or formatting.
- Algorithm correctness (sort, dedup, merge, parse).
- A regex or validation function that accepts or rejects input wrongly.

**Rust template:**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn task_id_parses_canonical_form() {
        let parsed: TaskId = "task-7f3a9c".parse().unwrap();
        assert_eq!(parsed.prefix(), TaskPrefix::Task);
        assert_eq!(parsed.short(), "7f3a9c");
    }

    #[test]
    fn task_id_rejects_missing_prefix() {
        let err = "7f3a9c".parse::<TaskId>().unwrap_err();
        assert!(matches!(err, TaskIdError::MissingPrefix));
    }
}
```

**Python template:**

```python
import pytest
from app.task import TaskId, TaskIdError

def test_task_id_parses_canonical_form():
    parsed = TaskId.parse("task-7f3a9c")
    assert parsed.prefix == "task"
    assert parsed.short == "7f3a9c"

def test_task_id_rejects_missing_prefix():
    with pytest.raises(TaskIdError, match="missing prefix"):
        TaskId.parse("7f3a9c")
```

**Smell that L1's wrong:** if writing the test needs you to construct more
than one or two collaborator objects, the bug crosses a boundary and
belongs at L2.

## Layer 2 — Component / integration

**What it is:** A test that crosses one module boundary, exercises
trait-object (or interface) wiring, or runs a real protocol message
through serialisation. The async runtime's real, but transport and
storage use in-memory fakes. No real network, no real disk.

**When the bug belongs here:**

- A request handler doesn't requeue or fail in-flight work on
  disconnect.
- A trait or interface implementation's behaviour differs from its
  contract.
- A serde round-trip mangles a field.
- An error from a lower layer maps to the wrong upper-layer error
  variant.
- A retry or backoff loop doesn't terminate.
- A cleanup / `Drop` / `__del__` doesn't fire under cancellation.

**Rust template:**

```rust
#[tokio::test]
async fn disconnect_requeues_inflight_tasks() {
    let db = InMemoryStore::new();
    let (mut dispatcher, link) = Dispatcher::with_fake_worker(&db);

    let task_id = dispatcher
        .dispatch(Task::new("compile"), WorkerId::new("worker-1"))
        .await
        .unwrap();

    link.simulate_disconnect();
    dispatcher.tick().await;

    let row: TaskRow = db.get("task", task_id).await.unwrap().unwrap();
    assert_eq!(row.status, TaskStatus::Failed);
    assert_eq!(row.failure_reason, Some(FailureReason::WorkerDisconnected));
}
```

**Python template:**

```python
import pytest
from app.dispatch import Dispatcher, Task, WorkerId, TaskStatus, FailureReason
from app.testing import InMemoryStore, FakeWorkerLink

@pytest.mark.asyncio
async def test_disconnect_requeues_inflight_tasks():
    db = InMemoryStore()
    dispatcher, link = Dispatcher.with_fake_worker(db)

    task_id = await dispatcher.dispatch(Task("compile"), WorkerId("worker-1"))
    link.simulate_disconnect()
    await dispatcher.tick()

    row = await db.get("task", task_id)
    assert row.status == TaskStatus.FAILED
    assert row.failure_reason == FailureReason.WORKER_DISCONNECTED
```

**Smell that L2's wrong:**

- The test needs a real TCP listener or a real database process → consider
  L3, or improve the in-memory fake.
- The test passes for the wrong reason because the fake doesn't model the
  real component's failure modes → either fix the fake (preferred) or
  escalate to L3.

## Layer 3 — BDD / workflow

**What it is:** End-to-end behaviour across multiple services with real
transport, real (possibly ephemeral) storage, real time. This is where
you prove the *system* does what the spec says, not just that individual
components do their parts.

**When the bug belongs here:**

- A multi-service workflow produces the wrong end state.
- The bug only manifests when message ordering across the transport
  reflects real network behaviour.
- A query against the real database interacts with real transaction
  semantics.
- The bug requires real `traceparent` propagation across a transport
  envelope.
- A spec scenario (Gherkin Given / When / Then) is the canonical artefact.

**Cucumber / Gherkin template:**

```gherkin
# features/dispatcher/worker_lifecycle.feature

Feature: Worker lifecycle resilience
  As an operator
  I want in-flight tasks recovered when a worker disconnects
  So that no work is silently lost

  Scenario: Worker disconnect mid-task requeues in-flight work
    Given a dispatcher with worker "compiler-1" connected
    And task "T-001" dispatched to "compiler-1"
    When "compiler-1" disconnects before sending a result
    Then task "T-001" should transition to status "failed"
    And a "task_failed" event should be persisted within 200ms
    And the failure reason should be "worker_disconnected"
```

Step definition skeletons exist in several BDD libraries (cucumber-rs,
behave, pytest-bdd). Pick the one that matches your project's runner.

**Smell that L3's wrong:** the test is *only* validating logic that could
be tested at L2 with an in-memory fake. L3 tests are expensive; reserve
them for genuine system-level behaviour.

## Layer 4 — Invariant / property

**What it is:** A test that asserts a property holds across a generated
input space (proptest, Hypothesis), or across all schedules of a
concurrent program (loom, shuttle). The point isn't to reproduce a
specific bug — it's to prove a *class* of bug can't occur.

**When the bug belongs here (in addition to L1/L2, never instead of):**

- The bug's an *invariant violation* — something that should always hold
  across all inputs or states (idempotency, monotonicity, conservation,
  round-tripping, ordering).
- The bug's a concurrency bug whose specific schedule's hard to reproduce
  deterministically.
- Once fixed, the bug defines a property the system must uphold forever,
  so future regressions get caught by the property rather than another
  example test.

**proptest template (Rust) — round-trip invariant:**

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn task_envelope_roundtrips(
        id in any::<u64>(),
        payload in prop::collection::vec(any::<u8>(), 0..4096),
    ) {
        let original = TaskEnvelope::new(TaskId::from(id), payload.clone());
        let encoded = original.encode();
        let decoded = TaskEnvelope::decode(&encoded).unwrap();
        prop_assert_eq!(decoded.id(), TaskId::from(id));
        prop_assert_eq!(decoded.payload(), payload.as_slice());
    }
}
```

**Hypothesis template (Python) — round-trip invariant:**

```python
from hypothesis import given, strategies as st
from app.envelope import TaskEnvelope, TaskId

@given(
    task_id=st.integers(min_value=0, max_value=2**64 - 1),
    payload=st.binary(min_size=0, max_size=4096),
)
def test_task_envelope_roundtrips(task_id, payload):
    original = TaskEnvelope(TaskId(task_id), payload)
    encoded = original.encode()
    decoded = TaskEnvelope.decode(encoded)
    assert decoded.id == TaskId(task_id)
    assert decoded.payload == payload
```

**Stateful template (Hypothesis):**

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

class DispatcherStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.dispatcher = Dispatcher.in_memory()
        self.dispatched = set()

    @rule(task_id=st.integers())
    def dispatch(self, task_id):
        self.dispatcher.dispatch(task_id)
        self.dispatched.add(task_id)

    @rule()
    def disconnect_worker(self):
        self.dispatcher.simulate_worker_disconnect()

    @invariant()
    def every_dispatched_task_has_terminal_row(self):
        for task_id in self.dispatched:
            row = self.dispatcher.get_row(task_id)
            assert row is None or row.status in {"completed", "failed"}, \
                f"task {task_id} stuck in {row.status if row else 'missing'}"

TestDispatcher = DispatcherStateMachine.TestCase
```

**loom template (Rust) — concurrency invariant:**

```rust
#[test]
fn shared_counter_no_lost_update() {
    loom::model(|| {
        let counter = Arc::new(AtomicU64::new(0));
        let t1 = {
            let c = counter.clone();
            loom::thread::spawn(move || c.fetch_add(1, Ordering::SeqCst))
        };
        let t2 = {
            let c = counter.clone();
            loom::thread::spawn(move || c.fetch_add(1, Ordering::SeqCst))
        };
        t1.join().unwrap();
        t2.join().unwrap();
        assert_eq!(counter.load(Ordering::SeqCst), 2);
    });
}
```

**Smell that L4's wrong:**

- The property's so loose it would've passed against the broken code.
  Tighten the invariant or pick a different property.
- The generator doesn't actually reach the buggy region of input space
  (proptest gives up after too many rejections). Constrain the generator
  to the relevant subspace.

## The layer decision tree

When you're writing the Phase 3 reproducer, walk this in order:

```
1. Is the bug in a pure function with no collaborators?
   YES → L1. Done.
   NO  → continue.

2. Does the bug cross exactly one module boundary, where an in-memory fake
   of the other module faithfully models the failure mode?
   YES → L2. Done.
   NO  → continue.

3. Does the bug require real transport, real persistence, or
   multi-service coordination?
   YES → L3 (Gherkin scenario or end-to-end test), AND consider whether
         the spec needs a new Scenario (Phase 7b / `/spec-create`).
   NO  → continue.

4. Is the bug an invariant violation that holds across a class of inputs
   or schedules?
   YES → ADD L4 (proptest / Hypothesis / loom / shuttle) IN ADDITION TO
         L1/L2/L3. Never replace an example test with a property test
         alone — examples are easier to debug when they fail.
   NO  → you have the right layer from steps 1-3.
```

## Running the right suites at each phase

**Phase 3 (reproducer creation):** run only the new test, fast.

```bash
# Rust
cargo test --package <crate> <test_name>
cargo nextest run --package <crate> -E 'test(<test_name>)'

# Python
pytest path/to/test.py::test_name -xvs
```

**Phase 5 (fix iteration):** still focused, plus the immediate
neighbourhood.

```bash
# Rust
cargo nextest run --package <crate>

# Python
pytest path/to/test_dir/ -x
```

**Phase 6 (full verification):** every applicable layer, in order of
speed.

```bash
# L1 + L2 (Rust)
cargo nextest run

# L1 + L2 (Python)
pytest

# L3 — BDD / workflow harness (Rust)
cargo test --features workflow --test bdd_runner

# L3 — BDD (Python)
pytest tests/bdd/
behave features/

# L4 — property + concurrency (Rust)
cargo test --features proptest -- proptest
RUSTFLAGS="--cfg loom" cargo test --release --test loom_tests

# L4 — property (Python)
pytest tests/property/ --hypothesis-seed=random
```

Any failure outside the reproducer counts as a regression. Investigate.
**Don't touch the failing test to make it pass.**

## Anti-patterns at each layer

**At L2 specifically — transport and storage:**

- Don't `sleep` waiting for a message. Use bounded channels with a
  `timeout` and assert the timeout doesn't fire.
- Don't bind to fixed ports. Use ephemeral ports (e.g. `tcp://*:0`,
  `inproc://`, OS-assigned port 0) and resolve the actual port post-bind.
- Each test gets its own context for stateful clients (database
  connections, message brokers, etc.). Sharing across tests is a
  flaky-test factory.
- Prefer in-memory backends for L2; reserve real backends for L3.
- Tests can't share a database namespace. Use a per-test UUID namespace
  or per-test in-memory instance.
- Don't assert on monotonic-time fields directly. Capture `before_time` /
  `after_time` and assert the row's timestamp's in range.

**At L3 specifically — multi-service:**

- Spin up only the services the scenario needs, not the whole fleet.
- Make sure cleanup is reliable — leaked processes between tests cause
  the worst flakes.
- Capture the full trace tree for any failure. See
  [observability-debug.md](observability-debug.md) for how.

**At L4 specifically — properties:**

- Use a `ReferenceModel` that captures the invariant without modelling
  every implementation detail. The reference model should be obviously
  correct; the implementation under test is what you're testing.
- For loom-style schedule exploration, isolate the state machine from the
  transport — model checkers don't scale to real I/O.

## Pyramid hygiene checklist

Before declaring the reproducer suite complete (end of Phase 3):

```
- [ ] Layer chosen per the decision tree, with a one-sentence justification
- [ ] If L3 was chosen, justification rules out L2 with in-memory fakes
- [ ] If L4 was added, an L1 or L2 example test was added alongside
- [ ] Test isolation: no shared state with other tests in the suite
- [ ] No `sleep`-based synchronisation; bounded timeouts where async
- [ ] Test names describe behaviour, not bug numbers
- [ ] At Phase 6, the corresponding layer's full suite runs, not just the
      new test
```

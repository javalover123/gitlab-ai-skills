# Root-cause research, reproduction, and live confirmation

Full detail for [SKILL.md](../SKILL.md) steps 2–4.

## 2. Research the root cause

Don't fix the symptom the issue names — find the shared place every
affected caller actually goes through.

- For an unfamiliar or large area, dispatch a subagent with one concrete
  question: given the symptom and any hint from the issue, trace the real
  code path end to end and report back the exact file:line, the mechanism,
  and why it produces the symptom. This keeps your own context clean for
  the fix that follows.
- Expect to need a second, more targeted pass. The first often lands one
  layer removed from the real mechanism — especially when seeded by the
  reporter's own guess. If the explanation doesn't fully account for the
  behavior, or points at a class/method that itself delegates further, dig
  one layer deeper.
- Still unclear after that: say so and ask a specific, options-based
  question rather than shipping a guess.
- Search scoped to the relevant directories (grep/ripgrep) rather than
  reading the whole repository — it's large. Don't re-read a file already
  in context.

## 3. Reproduce with a spec

Add a failing example to the most relevant *existing* spec file, next to
similar coverage, rather than a new file. Run it and confirm it fails for
the reason your root-cause theory predicts — a failure from unrelated
environment drift (pending migrations, a missing gem) isn't evidence about
the bug; fix the drift (`bin/rails db:migrate`, `bundle install`) and
rerun.

## 4. Confirm it live

Independent evidence that the bug isn't just an artifact of the spec's
mocks. Make sure the relevant local services are running, then write a
small **read-only** script (e.g. via `bin/rails runner`) that exercises the
real classes in memory — most service/policy-layer bugs need no database
writes, so prefer constructing objects directly over factories plus real
records. Keep scratch scripts out of your diff (a gitignored `tmp/` path is
fine).

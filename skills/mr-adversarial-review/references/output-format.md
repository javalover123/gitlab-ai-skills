# Output Format — Worked Example

This is the canonical example of a well-formed adversarial review comment. Match this shape exactly when posting.

The example below was the seed for this skill — a real adversarial review on a small CI-setup MR. It illustrates: a concise framing paragraph, severity-bucketed findings with bold headings, a "what is done well" bullet list, and a one-sentence summary.

---

## Adversarial Review: Add standalone CI with gem-release component

Overall this is a clean, well-scoped MR. The intent is clear and the pipeline is already green. Below are the issues I found, ordered by severity.

---

### 🔴 High

**Ruby version is hard-coded and will silently go stale**

`image: ruby:3.2` is pinned to a minor version but not a patch. More importantly, it will diverge from whatever the gemspec declares as the minimum supported Ruby. When Ruby 3.2 reaches EOL the image will still be pulled (it won't disappear from Docker Hub), so CI will keep passing against an unsupported runtime without anyone noticing. Consider:
- Deriving the version from the gemspec (e.g. via a matrix or a variable), or
- At minimum adding a comment that this must be kept in sync with the gemspec's `required_ruby_version`.

---

### 🟠 Medium

**No `allow_failure` or `needs` relationship between `rspec` and `rubocop`**

Both jobs are in `stage: test` and run in parallel, which is fine. However, if `rspec` fails, `rubocop` still runs (and vice versa). That is usually the desired behaviour, but there is no explicit `allow_failure: false` to document the intent, and no fast-fail strategy. More importantly, there is no `needs: []` to make them independent of each other explicitly — relying on implicit stage parallelism is fragile if stages are reordered later.

**No `retry` or timeout defined**

Transient runner failures (network blips during `bundle install`) will fail the whole pipeline with no retry. A `retry: 1` on the `default` block or per-job would improve resilience at no cost.

**`bundle install --jobs 4` is hard-coded**

The job count `4` may not match the runner's CPU count. Prefer `--jobs $(nproc)` or omit `--jobs` to let Bundler use its own default.

---

### 🟡 Low / Nitpicks

**Cache key covers only the gemspec, not `Gemfile`**

The previous GitLab Duo review flagged the missing `Gemfile.lock` (resolved by the author with the explanation that this gem intentionally omits the lockfile). That is a valid convention for published gems. However, the `Gemfile` itself is also not in the cache key. If someone adds a new group or source to `Gemfile` without touching the gemspec, the cache will not be invalidated. Adding `Gemfile` to the key costs nothing:
```yaml
key:
  files:
    - gitlab-grape-openapi.gemspec
    - Gemfile
```

**`stages` declaration is redundant given the component**

The `gem-release` component likely declares its own `deploy` stage internally. Declaring `stages: [test, deploy]` here works, but if the component ever adds a new stage the local declaration will shadow it silently. Worth checking the component's interface to see if stage declaration should be left to the component.

---

### ✅ What is done well

- Component version is pinned to `1.1.0` (previous `~latest` concern was already addressed).
- `before_script` is in the `default` block, so it applies consistently to all jobs.
- `force_remove_source_branch: true` is set, keeping the repo tidy.
- The MR is narrowly scoped: CI setup + rubocop directive cleanup only.
- Pipeline is green.

---

**Summary:** The MR is mergeable as-is, but the hard-coded Ruby version is the one issue worth addressing before merge to avoid silent drift. The medium items are worth a follow-up issue if not fixed here.

---

## Why this shape

- **Framing paragraph first** — readers calibrate expectations before the findings list. "Mergeable as-is" vs. "needs rework" up front.
- **Severity buckets in fixed order** (🔴 → 🟠 → 🟡 → ✅) — predictable scanning. Skip empty buckets entirely; absence is the signal.
- **Bold heading per finding** — scannable; readers can decide which findings to read in detail.
- **Code blocks where they help, prose where they don't** — don't over-format prose findings into nested bullets.
- **"What is done well" is not optional padding** — it tells the author which decisions you considered and endorsed.
- **Summary line is one sentence** — the takeaway, not a recap.

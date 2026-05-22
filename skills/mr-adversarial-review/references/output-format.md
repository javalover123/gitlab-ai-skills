# Output Format — Worked Example

Canonical example of a well-formed adversarial review comment. Match this shape exactly.

The example below was the seed for this skill — a real adversarial review on a small CI-setup MR.

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

**No `retry` or timeout defined**

Transient runner failures (network blips during `bundle install`) will fail the whole pipeline with no retry. A `retry: 1` on the `default` block or per-job would improve resilience at no cost.

**`bundle install --jobs 4` is hard-coded**

The job count `4` may not match the runner's CPU count. Prefer `--jobs $(nproc)` or omit `--jobs` to let Bundler use its own default.

---

### 🟡 Low / Nitpicks

**Cache key covers only the gemspec, not `Gemfile`**

The previous Duo review flagged the missing `Gemfile.lock`; the author confirmed this gem intentionally omits the lockfile. However, `Gemfile` itself is also not in the cache key — adding a new group or source to `Gemfile` without touching the gemspec won't invalidate the cache. Adding it costs nothing:

```yaml
key:
  files:
    - gitlab-grape-openapi.gemspec
    - Gemfile
```

---

### ✅ What is done well

- Component version is pinned to `1.1.0` (previous `~latest` concern was addressed).
- `before_script` is in the `default` block, so it applies consistently to all jobs.
- `force_remove_source_branch: true` keeps the repo tidy.
- The MR is narrowly scoped: CI setup + rubocop directive cleanup only.

---

**Summary:** Mergeable as-is, but the hard-coded Ruby version is worth addressing before merge to avoid silent drift.

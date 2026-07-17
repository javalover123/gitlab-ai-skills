Yes, this is worth checking. A new layout, lazy-loaded components, and a changed JS bundle all directly affect how the page renders in the browser, so this is a frontend / Core Web Vitals question, not a backend load question. The risk is real: a bigger or restructured bundle can push out how long the main thread is blocked, and a new layout with content that streams in via lazy-loading is a classic source of layout shift.

Here's what I'd do.

## 1. First, check whether a test already exists

Before setting anything up, search the repo so you're not duplicating existing coverage:

- Grep `.gitlab-ci.yml` and `.gitlab/ci/**` for `sitespeed`, `performance`, or `k6`.
- If there's already a Sitespeed Runway config for the project overview page, just re-run it and compare against its stored baseline instead of building something new.

If there's already a config, point your manager at that instead of a fresh test.

## 2. Use the right tool: Sitespeed Runway

For frontend page-load and Core Web Vitals, the GitLab tool to use is **Sitespeed Runway** (https://gitlab.com/gitlab-org/quality/sitespeed-runway). It's a hosted sitespeed.io service, so there's no local setup required, and it gives you FCP, LCP, TBT, and CLS directly.

To be clear on what I'm *not* recommending: this is not a k6/GPT job (that's for API/backend load) and not CPT (component-level MR testing). Your change is what the browser sees, so it needs a browser-based measurement.

## 3. Measure before vs. after

The whole point is a comparison, so measure both states:

- **Baseline:** run the old version of the page first (e.g. before your branch merges, or against the currently-deployed version) and record the numbers.
- **New:** run your redesigned version the same way.

Two things to get right so the numbers mean something:

- **Throttle the network** — use cable (or 3g) connectivity. Without throttling you're just measuring network jitter.
- **Run multiple iterations** — 5 to 11 runs per version. A single run has too much variance to trust; multiple runs give you a stable median.

Quickest path is the Web UI at https://sitespeed.runway.gitlab.net/ — enter the URL, pick chrome + cable + ~7 iterations, run it for both versions, and compare. If you'd rather automate/repeat it, there's a Docker/API option in the self-service docs (https://gitlab.com/gitlab-org/quality/sitespeed-runway/-/blob/main/docs/self-service.md).

## 4. What "worse" means — the thresholds to watch

For a change like this, watch these three especially:

| Metric | "Good" target | Why it matters here |
|---|---|---|
| **LCP** (Largest Contentful Paint) | < 2.5s | New layout can change which element is "largest" and when it renders |
| **CLS** (Cumulative Layout Shift) | < 0.1 | Lazy-loaded components are the #1 cause of layout shift — content popping in and shoving other content around |
| **TBT** (Total Blocking Time) | < 200ms | A changed/larger JS bundle can block the main thread longer |

Also glance at FCP (< 1.8s) and SpeedIndex (< 3.4s).

Two ways to judge the result, use both:
- **Absolute:** are the new numbers still inside the "good" targets above (Google's thresholds)?
- **Relative:** did any metric get meaningfully worse than the old page? Even if you're still under target, a jump in TBT or CLS from the bundle/lazy-loading is exactly what your manager is asking about.

If CLS specifically regressed, reserve space for the lazy-loaded components (fixed height / skeleton placeholders) so they don't shift content when they arrive.

## Important: don't test against staging or production

Point Sitespeed Runway at a review app or a dedicated environment — not staging or production. Frontend load testing is lower-risk than backend load, but the shared-environment rule still holds, and it's the cleaner way to get a stable comparison anyway.

## If you get stuck

Login/API-key access lives in 1Password ("Sitespeed Runway Production"). For access issues or anything beyond this, ping **#g_performance_enablement** on Slack — that's the Performance Enablement team and they own the tool.

Net: run the old and new versions of the project overview page through Sitespeed Runway with throttling and multiple iterations, compare LCP / CLS / TBT, and you'll have a concrete before/after answer for your manager rather than a gut feel.

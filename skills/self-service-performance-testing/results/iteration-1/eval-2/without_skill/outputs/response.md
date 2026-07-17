Yes, this is worth testing. A layout redesign plus a changed JS bundle and lazy-loaded components is exactly the kind of change that moves frontend performance, so your manager's instinct is right.

Since this is a page/frontend change (not an API or backend one), the metric that matters is Core Web Vitals, and the tool for that at GitLab is Sitespeed Runway (our hosted sitespeed.io service). You don't add test files to your repo for this — you run it against a deployed page.

## The one rule that matters first

Do NOT point this at staging or production. Performance tests generate load and can take a shared environment offline, which blocks everyone's deployments. Run against a dedicated performance environment or a review app. If you don't have one, ask in #g_performance_enablement and they'll help you set one up.

## What to do

The core method is a before/after comparison. You need to measure the OLD page and the NEW page under identical conditions, because a single run tells you nothing without a baseline to compare against.

1. Get the baseline first. Before your redesign is live, measure the current page. If it's already merged, measure the old version from a review app or a commit before the change. Either way you need both numbers.

2. Measure both with the same settings. The quickest path is the Web UI at https://sitespeed.runway.gitlab.net/:
   - Enter the page URL
   - Browser: Chrome
   - Connectivity: cable (throttling is essential — without it results just reflect network jitter and aren't comparable)
   - Iterations: 5 or more (a single run has high variance; 5-11 runs gives you stable numbers)
   - Run it for both the old and new page and compare.

   Login credentials are in 1Password under "Sitespeed Runway Production"; ping #g_performance_enablement if you need access. There's also a Docker/API path if you'd rather automate it.

3. Compare these metrics (before vs after):

   | Metric | "Good" target | Why it matters for your change |
   |---|---|---|
   | LCP (Largest Contentful Paint) | < 2.5s | New layout — did the main content render slower? |
   | FCP (First Contentful Paint) | < 1.8s | When does the first thing appear? |
   | CLS (Cumulative Layout Shift) | < 0.1 | Lazy-loaded components are the classic cause of layout shift — watch this closely |
   | TBT (Total Blocking Time) | < 200ms | Directly reflects your new JS bundle — more/heavier JS blocks the main thread |
   | SpeedIndex | < 3.4s | How fast the page visually fills in |

## How to judge "worse"

Use both a regression check and the absolute targets above:
- Absolute: LCP under 2.5s and CLS under 0.1 are Google's "good" thresholds. If the new page busts those, that's a clear regression regardless of the old numbers.
- Relative: compare the new page's LCP/FCP/TBT against the baseline. Given lazy-loading and a new bundle, TBT and CLS are the two I'd expect to move most — those are where I'd look first.

If the new page is worse, the metric that regressed usually points at the cause: TBT up means the JS bundle got heavier; CLS up means lazy-loaded components are shifting layout as they arrive (a placeholder/reserved-space fix usually solves it); LCP up means the largest element (often an image or hero block) is rendering later.

## Wiring it in going forward

For a one-time manager check, the Web UI comparison above is enough. If you want to catch this automatically on future changes to this page, you can add a sitespeed.io job to CI via the Docker/API path so a CWV budget is enforced on every MR — happy to help you set that up.

If you hit anything or want a second set of eyes on the numbers, #g_performance_enablement is the place to ask.

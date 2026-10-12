# Sitespeed Runway

**Repo:** https://gitlab.com/gitlab-org/quality/sitespeed-runway
**Self-service docs:** https://gitlab.com/gitlab-org/quality/sitespeed-runway/-/blob/main/docs/self-service.md
**Web UI:** https://sitespeed.runway.gitlab.net/
**CI integration examples:** https://gitlab.com/gitlab-org/quality/sitespeed-runway/-/blob/main/docs/ci-integration.md

Sitespeed Runway is a hosted sitespeed.io service for measuring frontend
performance (FCP, LCP, TBT, CLS, SpeedIndex). It provides a Web UI for
manual testing and an API for automated testing.

## How to Use It

**Option 1: Web UI** (quickest)
1. Go to https://sitespeed.runway.gitlab.net/
2. Enter the target URL
3. Configure: browser, iterations, connectivity (3g/4g/cable)
4. Run and view results

**Option 2: API via Docker** (recommended for automation)
```bash
docker run --cap-add=NET_ADMIN --shm-size=3g \
  -v "$(pwd):/sitespeed.io" \
  sitespeedio/sitespeed.io:37-plus1 \
  --api.hostname sitespeed.runway.gitlab.net \
  --api.port 443 \
  --api.location default \
  --api.action addAndGetResult \
  --api.key YOUR_API_KEY \
  -b chrome \
  https://your-app.example.com/page
```

**Option 3: Local Node.js**
```bash
sitespeed.io https://your-app.example.com/page \
  --api.hostname sitespeed.runway.gitlab.net \
  --api.port 443 \
  --api.location default \
  --api.action addAndGetResult \
  --api.key YOUR_API_KEY \
  --browsertime.browser chrome \
  --browsertime.iterations 3
```

## Key Metrics and Targets

| Metric | Target | What it measures |
|---|---|---|
| FCP (First Contentful Paint) | < 1.8s | Time until first content appears |
| LCP (Largest Contentful Paint) | < 2.5s | Time until largest element renders |
| TBT (Total Blocking Time) | < 200ms | Main thread blocking between FCP and TTI |
| CLS (Cumulative Layout Shift) | < 0.1 | Visual stability |
| SpeedIndex | < 3.4s | How quickly content visually populates |
| TTFB (Time to First Byte) | < 600ms | Server response time |

## When to Use Sitespeed Runway

- Measuring Core Web Vitals for new or changed pages
- Comparing page load performance before/after a change
- Monitoring frontend performance trends over time

## When NOT to Use Sitespeed Runway

- API/backend load testing → use GPT
- Component-level MR testing → use CPT

## Access

Login credentials are in 1Password under "Sitespeed Runway Production."
API key required for automated testing. Contact **#g_performance_enablement**
if you need access.

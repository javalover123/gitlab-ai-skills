# Frontend Performance with sitespeed.io

Guide for measuring Core Web Vitals. **Start with Sitespeed Runway** — GitLab's
hosted sitespeed.io service at https://sitespeed.runway.gitlab.net/ — rather
than setting up sitespeed.io from scratch. See ptk-tools.md via the main skill's
routing table for Runway setup and access.

This reference covers sitespeed.io configuration, throttling, budgets, and
gotchas that apply whether you're using Runway or running locally.

## When to Test Frontend Performance

| Change | Test? | What to Measure |
|---|---|---|
| New page added | Yes | LCP, FCP, CLS, TBT, SpeedIndex |
| Major layout change | Yes | CLS (layout shifts), LCP |
| Large JS bundle added/changed | Yes | TBT, SpeedIndex |
| New third-party script | Yes | TBT, transfer size, request count |
| Image-heavy page update | Yes | LCP, transfer size |
| CSS refactor | Yes | FCP, SpeedIndex |
| Backend-only API change | No | Use k6 instead |
| Copy/text change (no layout impact) | No | No visual metric impact |

## Non-Negotiable Rules

- **Always pin Docker version** (e.g., `sitespeedio/sitespeed.io:39.4.2`).
  Never `:latest` - version drift corrupts trend data.
- **Always throttle connectivity** (`-c cable` or `-c 3g`). Without it, results
  reflect network jitter, not page performance.
- **Run 5+ iterations** per URL (`-n 5` minimum, 7-11 for stable metrics).
- **Always record video** (`--video --visualMetrics`) for SpeedIndex.
- **Never test against staging or production.**

## Throttling Setup

### Linux (recommended)

```bash
sudo modprobe ifb numifbs=1

docker run --cap-add=NET_ADMIN --rm -v "$(pwd):/sitespeed.io" \
  sitespeedio/sitespeed.io:39.4.2 \
  -c cable \
  --browsertime.connectivity.engine throttle \
  https://your-app.example.com/
```

### macOS

Throttle outside Docker:

```bash
npm install @sitespeed.io/throttle -g
throttle cable
docker run --rm -v "$(pwd):/sitespeed.io" \
  sitespeedio/sitespeed.io:39.4.2 \
  https://your-app.example.com/
throttle stop
```

### Connectivity profiles

| Profile | Bandwidth | Latency | Use for |
|---|---|---|---|
| `cable` | 5 Mbit | 14ms | Desktop users on broadband |
| `3g` | 1.6 Mbit | 150ms | Mobile users on 3G |
| `3gslow` | 0.4 Mbit | 200ms | Worst-case mobile |

## Performance Budget

```json
{
  "budget": {
    "googleWebVitals": {
      "firstContentfulPaint": 1800,
      "largestContentfulPaint": 2500,
      "totalBlockingTime": 300,
      "cumulativeLayoutShift": 0.1
    }
  }
}
```

Budget failures produce exit code > 0 (CI-friendly). Use `--budget.output junit`
for GitLab CI test report integration.

For per-URL overrides (when one page is expected to be slower), add the URL as
a key in the budget object with its own thresholds.

## CLS Gotcha: Scroll the Page

Many layout shifts happen below the fold. For accurate CLS, use a scripted
journey that scrolls:

```javascript
module.exports = async function (context, commands) {
  await commands.measure.start('homepage');
  await commands.navigate('https://your-app.example.com/');
  await commands.js.run('window.scrollTo(0, document.body.scrollHeight)');
  await commands.wait.byTime(2000);
  await commands.measure.stop();
};
```

Run with `--multi journey-script.js`.

## Calibrating Against CrUX Data

Compare synthetic metrics against real user data (75th percentile):

```bash
docker run --rm -v "$(pwd):/sitespeed.io" \
  sitespeedio/sitespeed.io:39.4.2 \
  --crux.key YOUR_CRUX_API_KEY \
  https://your-app.example.com/
```

Adjust connectivity settings until your FCP and LCP align with CrUX P75
values. This ensures your synthetic tests reflect real-world experience.

## GitLab CI Integration

```yaml
frontend_perf:
  stage: performance
  image:
    name: sitespeedio/sitespeed.io:39.4.2
    entrypoint: ['']
  script:
    - /start.sh
      --budget.configPath /sitespeed.io/budget.json
      --budget.output junit
      -n 5
      -b chrome
      https://${CI_ENVIRONMENT_URL}/
  artifacts:
    paths:
      - sitespeed-result/
    reports:
      junit: sitespeed-result/**/junit.xml
    when: always
  rules:
    - if: $CI_MERGE_REQUEST_IID
      changes:
        - app/views/**/*
        - app/assets/**/*
        - app/javascript/**/*
  tags:
    - your-perf-runner-tag
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| No connectivity throttling | Always use `-c cable` or `-c 3g` |
| Using `:latest` Docker tag | Pin exact version (e.g., `39.4.2`) |
| Only 1 run per URL | Use `-n 5` minimum, 7-11 for stable metrics |
| Not scrolling for CLS | Use scripting to scroll the page |
| Comparing metrics across tools | Only compare within the same tool over time |
| Testing without video | Always add `--video --visualMetrics` |
| No budget file | Create budget.json with Google Web Vitals thresholds |
| Testing against staging | Use dedicated perf environment only |

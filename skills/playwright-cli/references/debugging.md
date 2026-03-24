# Debugging

## Inspect console and network

```bash
pw console                  # all console messages
pw console warning          # filter: log, info, warning, error
pw network                  # all requests since last page load
```

## Screenshots and PDF

```bash
pw screenshot               # screenshot of viewport
pw screenshot e5            # screenshot of specific element
pw screenshot --filename=page.png
pw pdf --filename=page.pdf
```

## Tracing (detailed debug trace)

```bash
pw tracing-start
# ... perform actions ...
pw tracing-stop
```

Trace files go in `.playwright-cli/traces/`. Each trace contains:
- DOM snapshot before/after every action
- Screenshots at each step
- Full network log (requests, headers, bodies, timing)
- Console messages

## Video recording

```bash
pw video-start
# ... perform actions ...
pw video-stop recording.webm
```

## Run arbitrary Playwright code

For anything the CLI doesn't expose:

```bash
pw run-code "async page => {
  // Full Playwright API available
  // Return value is printed as output
  return await page.title();
}"
```

Common uses:
- Access `page.context()` for permissions, geolocation
- Wait for complex conditions
- Access iframes
- Handle file downloads
- Inspect page internals

## DevTools

```bash
pw show         # open browser DevTools (headed mode only)
pw devtools-start
```

## Debugging checklist

1. **Page not loading?** Check URL, try `pw reload`
2. **Element ref not found?** Take fresh `pw snapshot` — refs reset after navigation
3. **Action seems to do nothing?** Use `pw console` to check JS errors
4. **Intermittent failures?** Add `waitForSelector` / `waitForLoadState` via `run-code`
5. **Stale browser?** `pw kill-all` then reopen
6. **Unexpected output or pw misbehaving?** Fall back to raw `playwright-cli` — same interface, unfiltered output

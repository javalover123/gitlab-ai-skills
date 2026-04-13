---
name: playwright-cli
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages.
version: 1.1.0
category: Testing
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: browser-automation
---

# Browser Automation

Use `scripts/pw` for all browser commands (it's in the skill's base directory shown above). It wraps `playwright-cli` with cleaner output: snapshots are inlined automatically (no separate Read call needed), JS code blocks are stripped, and noise is removed.

If `scripts/pw` produces unexpected output or behaves incorrectly, fall back to raw `playwright-cli` — it has the exact same interface but shows unfiltered output, which can help diagnose what's happening.

## Navigate and interact

```bash
scripts/pw open https://example.com   # open browser → URL + inline snapshot
scripts/pw goto https://other.com     # navigate (browser already open) → snapshot
scripts/pw click e8                   # click element → URL + inline snapshot
scripts/pw fill e5 "text"             # fill input (silent = success)
scripts/pw type "text"                # type into focused element (silent = success)
scripts/pw press Enter                # keyboard press (silent = success)
scripts/pw snapshot                   # refresh snapshot (after SPA content change)
scripts/pw close                      # always close when done
```

## Reading the snapshot

Every `scripts/pw open`, `scripts/pw goto`, and `scripts/pw click` shows an inline ARIA tree. Read the refs:

```
- textbox "Email" [ref=e5]     → scripts/pw fill e5 "user@example.com"
- button "Sign in" [ref=e8]    → scripts/pw click e8
- link "Forgot password" [ref=e3] → scripts/pw click e3
- combobox "Country" [ref=e12] → scripts/pw select e12 "US"
- checkbox "Remember me" [ref=e6] → scripts/pw check e6
```

Refs are valid until the next navigation. After `scripts/pw click` navigates, use the new snapshot in that output — no extra `scripts/pw snapshot` needed.

## More commands

```bash
scripts/pw check e6   # or: scripts/pw uncheck e6   # checkbox
scripts/pw select e9 "value"                # dropdown
scripts/pw dblclick e7   # or: scripts/pw hover e4  # mouse
scripts/pw screenshot                       # saves PNG, outputs path
scripts/pw screenshot e5                    # element screenshot
scripts/pw screenshot --filename=out.png    # named file
scripts/pw state-save auth.json             # save auth state (cookies + localStorage)
scripts/pw state-load auth.json             # restore auth state
scripts/pw go-back   # or: scripts/pw go-forward, scripts/pw reload
scripts/pw tab-new https://url   # also: scripts/pw tab-list, scripts/pw tab-select 2
scripts/pw route "**/*.jpg" --status=404    # mock network requests
scripts/pw run-code "async page => { ... }" # arbitrary Playwright JS
```

## Dialogs (set handler BEFORE triggering the dialog)

```bash
scripts/pw dialog-accept          # accept next alert/confirm
scripts/pw dialog-accept "text"   # type into prompt then accept
scripts/pw dialog-dismiss         # dismiss
# now trigger the action that opens the dialog
scripts/pw click e5
```

## Named sessions (isolated cookies/storage)

```bash
scripts/pw -s=user1 open https://app.com
scripts/pw -s=user2 open https://app.com
scripts/pw list   # also: scripts/pw close-all, scripts/pw kill-all
```

## Iframes

`scripts/pw` commands don't cross iframe boundaries — use `scripts/pw run-code`:

```bash
scripts/pw run-code "async page => {
  const frame = page.locator('iframe#id').contentFrame();
  await frame.locator('button').click();
}"
```

## When to call scripts/pw snapshot explicitly

- After SPA route change (URL didn't change but content did)
- After a modal/drawer opens
- When a ref returns "Ref eN not found" — take fresh snapshot to get updated refs

## References (load on demand)

- [`references/advanced-interactions.md`](references/advanced-interactions.md) — waiting, file upload/download, drag, permissions, emulation
- [`references/network-mocking.md`](references/network-mocking.md) — route patterns, conditional responses, inspecting requests
- [`references/storage.md`](references/storage.md) — cookies, localStorage, sessionStorage details
- [`references/debugging.md`](references/debugging.md) — tracing, video recording, console/network inspection
- [`references/sessions.md`](references/sessions.md) — multi-session patterns, persistent profiles, tabs, config

## Contributing Improvements

If you discover that any guidance in this skill is **inaccurate or outdated** (e.g., a command that no longer works, a wrong flag, incorrect filtering behavior), confirm with the user and open an MR to `gitlab-org/ai/skills` with the fix. Keep changes focused — one fix per MR.

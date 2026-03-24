---
name: playwright-cli
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages.
version: 1.0.0
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: browser-automation
---

# Browser Automation

Use `pw` for all browser commands. It wraps `playwright-cli` with cleaner output: snapshots are inlined automatically (no separate Read call needed), JS code blocks are stripped, and noise is removed.

If `pw` produces unexpected output or behaves incorrectly, fall back to raw `playwright-cli` — it has the exact same interface but shows unfiltered output, which can help diagnose what's happening.

## Navigate and interact

```bash
pw open https://example.com   # open browser → URL + inline snapshot
pw goto https://other.com     # navigate (browser already open) → snapshot
pw click e8                   # click element → URL + inline snapshot
pw fill e5 "text"             # fill input (silent = success)
pw type "text"                # type into focused element (silent = success)
pw press Enter                # keyboard press (silent = success)
pw snapshot                   # refresh snapshot (after SPA content change)
pw close                      # always close when done
```

## Reading the snapshot

Every `pw open`, `pw goto`, and `pw click` shows an inline ARIA tree. Read the refs:

```
- textbox "Email" [ref=e5]     → pw fill e5 "user@example.com"
- button "Sign in" [ref=e8]    → pw click e8
- link "Forgot password" [ref=e3] → pw click e3
- combobox "Country" [ref=e12] → pw select e12 "US"
- checkbox "Remember me" [ref=e6] → pw check e6
```

Refs are valid until the next navigation. After `pw click` navigates, use the new snapshot in that output — no extra `pw snapshot` needed.

## More commands (all via pw)

```bash
pw check e6   # or: pw uncheck e6         # checkbox
pw select e9 "value"                # dropdown
pw dblclick e7   # or: pw hover e4        # mouse
pw screenshot                       # saves PNG, outputs path
pw screenshot e5                    # element screenshot
pw screenshot --filename=out.png    # named file
pw state-save auth.json             # save auth state (cookies + localStorage)
pw state-load auth.json             # restore auth state
pw go-back   # or: pw go-forward, pw reload
pw tab-new https://url   # also: pw tab-list, pw tab-select 2
pw route "**/*.jpg" --status=404    # mock network requests
pw run-code "async page => { ... }" # arbitrary Playwright JS
```

## Dialogs (set handler BEFORE triggering the dialog)

```bash
pw dialog-accept          # accept next alert/confirm
pw dialog-accept "text"   # type into prompt then accept
pw dialog-dismiss         # dismiss
# now trigger the action that opens the dialog
pw click e5
```

## Named sessions (isolated cookies/storage)

```bash
pw -s=user1 open https://app.com
pw -s=user2 open https://app.com
pw list   # also: pw close-all, pw kill-all
```

## Iframes

`pw` commands don't cross iframe boundaries — use `pw run-code`:

```bash
pw run-code "async page => {
  const frame = page.locator('iframe#id').contentFrame();
  await frame.locator('button').click();
}"
```

## When to call pw snapshot explicitly

- After SPA route change (URL didn't change but content did)
- After a modal/drawer opens
- When a ref returns "Ref eN not found" — take fresh snapshot to get updated refs

## References (load on demand)

- [`references/advanced-interactions.md`](references/advanced-interactions.md) — waiting, file upload/download, drag, permissions, emulation
- [`references/network-mocking.md`](references/network-mocking.md) — route patterns, conditional responses, inspecting requests
- [`references/storage.md`](references/storage.md) — cookies, localStorage, sessionStorage details
- [`references/debugging.md`](references/debugging.md) — tracing, video recording, console/network inspection
- [`references/sessions.md`](references/sessions.md) — multi-session patterns, persistent profiles, tabs, config

## Setup

`pw` is at `~/.agents/skills/playwright-cli/scripts/pw` (symlinked to `~/bin/pw`).
If the binary is missing: `npm install -g playwright-cli && npx playwright install chrome`.

## Contributing Improvements

If you discover that any guidance in this skill is **inaccurate or outdated** (e.g., a command that no longer works, a wrong flag, incorrect filtering behavior), confirm with the user and open an MR to `gitlab-org/ai/skills` with the fix. Keep changes focused — one fix per MR.

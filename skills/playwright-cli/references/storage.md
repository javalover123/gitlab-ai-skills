# Storage Management

## Browser state (cookies + localStorage)

```bash
# Save complete auth state to file
pw state-save auth.json
pw state-save   # auto-generated filename

# Restore state (then navigate — cookies apply on next page load)
pw state-load auth.json
pw goto https://app.example.com   # now authenticated
```

State file contains all cookies and localStorage for all origins.

## Cookies

```bash
pw cookie-list                   # all cookies
pw cookie-list --domain=example.com
pw cookie-get session_id
pw cookie-set session_id abc123
pw cookie-set session_id abc123 --domain=example.com --httpOnly --secure --sameSite=Lax
pw cookie-delete session_id
pw cookie-clear                  # clear all
```

## localStorage

```bash
pw localstorage-list
pw localstorage-get theme
pw localstorage-set theme dark
pw localstorage-set settings '{"theme":"dark","lang":"en"}'   # JSON value
pw localstorage-delete theme
pw localstorage-clear
```

## sessionStorage

```bash
pw sessionstorage-list
pw sessionstorage-get step
pw sessionstorage-set step 3
pw sessionstorage-delete step
pw sessionstorage-clear
```

## Multiple cookies at once

```bash
pw run-code "async page => {
  await page.context().addCookies([
    { name: 'session', value: 'abc123', domain: 'example.com', path: '/', httpOnly: true },
    { name: 'prefs', value: '{\"theme\":\"dark\"}', domain: 'example.com', path: '/' }
  ]);
}"
```

## Security

- Never commit state files with auth tokens
- Add `*.auth-state.json` to `.gitignore`
- Sessions run in-memory by default (safer); use `--persistent` to persist to disk

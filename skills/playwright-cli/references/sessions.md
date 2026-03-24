# Browser Sessions

## Named sessions

Use `-s` to isolate browser contexts (separate cookies, storage, history):

```bash
pw -s=user1 open https://app.example.com
pw -s=user2 open https://app.example.com

pw -s=user1 fill e1 "alice@example.com"
pw -s=user2 fill e1 "bob@example.com"

pw list          # show all active sessions
pw close-all     # close all sessions
pw kill-all      # force-kill stale/zombie processes
```

## Default session variable

```bash
export PLAYWRIGHT_CLI_SESSION="myapp"
pw open https://example.com   # uses "myapp" session automatically
```

## Persistent profiles

By default, sessions are in-memory (wiped on close). For persistent logins:

```bash
pw open https://example.com --persistent          # auto location
pw open https://example.com --profile=/path/to/dir  # custom dir
pw delete-data   # clear persistent data
```

## Browser selection

```bash
pw open --browser=chrome     # default
pw open --browser=firefox
pw open --browser=webkit
pw open --browser=msedge
pw open --browser=chromium   # open source Chromium (no Chrome)
```

## Tabs within a session

```bash
pw tab-list
pw tab-new https://example.com
pw tab-select 0             # zero-indexed
pw tab-close                # close current tab
pw tab-close 2              # close tab by index
```

## Config file

```bash
pw open https://example.com --config=my-config.json
```

## Parallel scraping example

```bash
pw -s=site1 open https://site1.com &
pw -s=site2 open https://site2.com &
wait
pw -s=site1 snapshot
pw -s=site2 snapshot
pw close-all
```

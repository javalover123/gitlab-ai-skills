# Draft Reviews (using `note` CLI)

The [`note`](https://gitlab.com/viktomas/note) CLI supports draft reviews — comments that stay invisible until explicitly published. Use drafts when you want to batch multiple comments before making them visible.

Install:

```bash
# See https://gitlab.com/viktomas/note for installation
go install gitlab.com/viktomas/note@latest
```

## Creating Drafts

### Draft replies to existing discussions

```bash
# Reply to a discussion as draft
note draft create --reply d1a2b3c4 -m ":robot: AI-generated

Good point, will fix."

# Reply and auto-resolve on publish
note draft create --reply d1a2b3c4 --resolve -m ":robot: AI-generated

Fixed in latest push."
```

### Draft comments on diff lines

```bash
# Draft diff comment on a specific line (new side)
note draft create --file main.go --line 42 -m ":robot: AI-generated

Nit: rename this"

# Multiline diff comment (lines 10 through 15)
note draft create --file main.go --line 10:15 -m ":robot: AI-generated

Refactor this block"

# Comment on a removed line (old side)
note draft create --file main.go --old-line 10 -m ":robot: AI-generated

Why was this removed?"
```

### Draft general comments

```bash
note draft create -m ":robot: AI-generated

Needs work"
```

### Multiline body via stdin

````bash
note draft create --file main.go --line 42 <<'EOF'
:robot: AI-generated

**Title of the finding**

Explanation of the problem.

```go
// suggested fix
```
EOF
````

## Managing Drafts

```bash
# List pending drafts
note draft list

# Publish all drafts (ONLY when user explicitly asks)
note draft publish
```

## Batch Review from JSON

Creates multiple draft comments at once:

```bash
# Creates drafts (don't add --publish without user approval)
echo '[{"file":"main.go","line":42,"body":":robot: AI-generated\n\nNit: rename this"}]' | note review
```

## Publishing Rules for Drafts

1. **Never run `note draft publish` without the user explicitly requesting it.**
2. After creating drafts, report what's pending and let the user decide when to publish.
3. Use drafts as the default when `note` CLI is available and the user wants to review comments before they go live.

## Auto-detection

Like `glab`, the `note` CLI auto-detects the project and MR from the current branch. Pass `--mr <iid>` only if auto-detection fails.

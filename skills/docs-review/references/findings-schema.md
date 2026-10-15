# Findings schema

The phase 2 scripts, `combine_findings.py`, `site_check.py` from
`docs-preview`, and every reviewer emit findings in this shape. The combine step
rejects anything else.

Contents:

- [File shape](#file-shape)
- [Finding fields](#finding-fields)
- [Reviewer output](#reviewer-output)
- [Importance](#importance)
- [Scope](#scope)
- [Severity](#severity)
- [Fixability](#fixability)

## File shape

```json
{
  "version": 1,
  "target": {"project": "group/project", "mr": 123, "base": "<sha>", "head": "<sha>"},
  "findings": [],
  "vocabulary": []
}
```

`vocabulary` is only in `docs_lint.py` output. See [vocabulary.md](vocabulary.md).

## Finding fields

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | `<reviewer or script>.<rule>`, for example `word-list.utilize` or `lint.history-format`. <!-- voice-ok: GitLab word list --> |
| `reviewer` | Yes | `editor`, `facts`, or `reader`, or a script: `lint`, `vale`, `word-list` (Vale product names), `markdownlint`, `impact`, or `docs-preview`. |
| `severity` | Yes | `blocker`, `major`, `minor`, or `nit`. |
| `importance` | Reviewers: yes | 1 to 5: how much the finding matters to the reader. See [Importance](#importance). Scripts set a default per rule. The combine step fills it when it is missing. |
| `importance_why` | With `importance` | One sentence, from the reader's side, that explains the level. |
| `why` | First-time writer | Editor and reader: one plain sentence on why the rule exists, for coaching. `source` is the link. |
| `occurrences` | No | The other lines of a repeated issue, `[{line, end_line, quote, suggestion, file, message}]`, always a list of objects. The finding's `message` must be true of every occurrence; give an occurrence its own `message` when the specifics differ, for example another page. Occurrences do not inherit `preservation`. The combine step expands them into one finding each (`occurrence_of`), which group into one comment. A bare line number, or an object without `quote`, takes the quote from that line of the file, with a warning. A count instead of a list is ignored. |
| `covers` | No | Ids of other findings on the same lines that this finding's suggestion also fixes. They fold into it. |
| `confidence` | Yes | `high`, `medium`, or `low`. |
| `file`, `line`, `end_line` | Yes | Path relative to the repo root. Lines in the head revision. |
| `quote` | Yes | Exact text from the file. Reviewers must copy it verbatim. The combine step drops a reviewer finding with no quote. |
| `message` | Yes | One line that names the rule, in the voice of a technical writer. |
| `source` | Yes | Link to the rule: a docs.gitlab.com anchor, or the reviewer file. |
| `suggestion` | No | Full replacement for `line` to `end_line`, ready for a suggestion block. |
| `fixable` | Yes | `auto`, `suggest`, or `manual`. |
| `deterministic` | Yes | `true` for scripts, `false` for reviewers. |
| `evidence` | facts, impact | List of `{kind, ref, note}`. `kind` is `code`, `test`, `cli`, `mr`, `issue`, `doc`, or `search`. Non-public evidence (confidential items, private or internal projects) is `{"ref": "non-public"}` with no details; `post_review.py` withholds any other reference it cannot confirm as public. |
| `verdict` | facts | `verified`, `contradicted`, or `unverified`. |
| `sme` | facts | Up to 2 `{username, reason}` entries, from `scripts/sme.py`. |
| `caused_by_line` | No | For a finding on an unchanged line, the changed line that made it wrong (`caused_by_file` when that line is on another page). See [Scope](#scope). |
| `summary_only` | No | `true` for page-level findings. They go in the summary, never inline. |
| `scope` | No | `line` (default), `section`, or `page`. A `page` finding is about the whole page, and is summary-only. |
| `needs_input` | No | `true` when the fix needs an answer from the author or an expert. Write the question in `message` as **Question:**. In auto mode only these findings are posted; a writer applies the rest. `lib/findings.needs_input` also treats a **Question:** message, and an `unverified` facts claim with no suggestion, as needing input. |
| `action` | No | `fix`, the only value. The combine step ignores any other value and notes it in `coerced`. |

## Reviewer output

Paste this section into every reviewer prompt. Each reviewer finding is one
JSON object with these fields:

- Required: `id` (`<reviewer>.<rule>`), `reviewer`, `severity` (`blocker`,
  `major`, `minor`, or `nit`), `confidence` (`high`, `medium`, or `low`),
  `importance` (1-5), `importance_why`, `file`, `line`, `end_line`, `quote`
  (verbatim text of those lines at the head), `message`, `source` (the rule
  link), `fixable` (`auto`, `suggest`, or `manual`), and
  `deterministic: false`.
- Optional: `suggestion` (the full replacement, `null`, or `""` to delete),
  `occurrences` (`[{line, end_line, quote, suggestion, file, message}]`), `covers`,
  `caused_by_line` and `caused_by_file`, `old_text: true` for a problem the
  old version also had (it goes to the summary), and `scope: "page"` for a
  page-level finding (no other value).
- `why` on every editor and reader finding for a first-time docs writer.
- facts: `verdict` and `evidence` (at least one `{kind, ref, note}`), and
  `sme` when the reviewer file says so.
- editor: `preservation` on every finding that removes, shortens, or
  reorders text.

A reviewer finding with no quote or no source is dropped.

## Importance

Importance is separate from severity (how strict the rule is) and from
confidence (how sure the reviewer is). It drives ranking and posting.

| Importance | Meaning | Examples |
|------------|---------|----------|
| 5 | The reader fails or gets a wrong result. | A wrong fact, a missing step, data loss, a missing redirect. |
| 4 | The reader is likely confused or misled. | A missing prerequisite, contradicting steps, a misleading heading, a broken link or anchor. |
| 3 | Noticeable friction. | Structure that hides the task, a vague verb, a long concept before the task. |
| 2 | Slower to scan. | A long sentence, bold for emphasis, minor wording, a word-list swap, history format. |
| 1 | A cosmetic preference. | Alert case, a missing code fence language. Never posted inline. |

A blocker is never below 4. Importance 1 never posts inline, and when the
author is not a first-time docs writer, the combine step also moves
non-blocker reader findings below importance 4 to the summary.

## Scope

Every finding gets a `scope_class`:

| Class | Meaning | Where it goes |
|-------|---------|---------------|
| `introduced` | On a line the MR changed, or on the heading of a changed section. | Inline. |
| `broken` | On an unchanged line that the change made wrong: a link to a heading the MR renamed, a flag alert for a flag the MR removes, a prerequisite list that misses the offering the MR adds. The finding names the changed line in `caused_by_line` (and `caused_by_file` when it is another page), and the script checks that the line changed. Findings from `impact.py`, `facts.impact.*`, and the `lint.anchor-broken` and `lint.redirect-*` checks are always `broken`. | Inline, and it can block. |
| `existing` | Anything else: a problem that was on the page before the MR. | The collapsed "Existing issues on this page" list in the summary. Never inline, never a blocker. |

A finding that is in scope posts inline when it cites a specific rule: a
guideline page or section (topic types, metadata, navigation, a style guide
section), or a word list entry. Blockers, facts, and script findings always
pass. An editor or reader finding whose source is empty, or only the style
guide or documentation root, has no specific rule behind it and goes to the
collapsed "Optional polish" list in the summary.

## Severity

When in doubt, pick the lower severity.

| Severity | Use for |
|----------|---------|
| `blocker` | Breaks the build, a broken link or anchor, a missing redirect, a wrong fact, a legal or product-name rule |
| `major` | A rule a technical writer would require before merge |
| `minor` | Should be fixed, but does not block |
| `nit` | Optional polish |

## Fixability

- `auto`: the fix is mechanical and safe, for example a word-list swap or a
  list marker. The fix loop applies it.
- `suggest`: a reviewer's rewrite. Posted as a suggestion block. The fix loop
  applies it only with `high` confidence.
- `manual`: a writer must make the edit, for example a structure change. When
  the fix needs an answer from the author or an expert, also set
  `needs_input: true`.

# Vocabulary triage

Vale flags words it does not know, and words that a substitution rule maps to
another word. Some flags are wrong: a product name, a third-party tool, or a
term from the UI. Never fix these blindly, and never turn off a whole rule to
silence one word. Decide in context, then use the narrowest fix.

Contents:

- [When to run](#when-to-run)
- [Decide](#decide)
- [Apply the narrowest fix](#apply-the-narrowest-fix)
- [Report](#report)

## When to run

The editor reviewer applies this file when it handles the `vocabulary`
array from `docs_lint.py` ([editor](reviewers/editor.md)). The array groups
every Vale finding from a spelling rule (`gitlab_base.Spelling`), the British
spelling rule (`gitlab_base.British`), or a substitution rule
(`Substitutions`, `SubstitutionWarning`) by term, with the number of hits
and the files, so each term is decided once per run. The editor returns
each decision as a finding and edits nothing. Exceptions are added later, in
the [fix loop](writer.md#fix-loop).

## Decide

Read two or three of the sentences that use the term, and check the term at
its source (the product UI, the project's code, or the official name of the
third-party technology). Then pick one row:

| The term is | Action |
|-------------|--------|
| A misspelling or a British spelling of a common word | Fix it. `fixable: auto`. |
| A word-list violation in context | Fix it, following the word list. |
| A command, variable, file name, or code | Put it in backticks. |
| The correctly capitalized name of a product, service, or technology (for example, a third-party tool) | Add an exception. See the next section. |
| UI text from GitLab that matches the product | Add an exception. If the UI text seems wrong, suggest an issue instead. |
| The name of a person, or UI text from a third-party product | Rewrite the sentence, or disable the rule inline for that line. |

GitLab's process for spelling exceptions is in the
[Vale testing guide](https://docs.gitlab.com/development/documentation/testing/vale/#spelling-test).

## Apply the narrowest fix

From narrow to broad. Stop at the first one that works:

1. For one line, disable the rule inline:
   `<!-- vale gitlab_base.Spelling = NO -->` before it and `= YES` after it.
1. For the `Spelling` rule, add the term to the exceptions list:
   - In the `gitlab` repository: `doc/.vale/gitlab_base/spelling-exceptions.txt`,
     in alphabetical order.
   - In another project: the project's Vale vocabulary
     (`<StylesPath>/config/vocabularies/<Name>/accept.txt`, with `Vocab = <Name>`
     in `.vale.ini`).
1. For a substitution rule such as `British`: the vocabulary does not help,
   because Vale applies substitution rules to accepted words too. Make the
   entry in the rule case-sensitive, so the proper noun passes and the common
   word is still caught. For example, in `British.yml` change
   `calibre: caliber` to `'(?-i)calibre': caliber`. Then "Calibre" (the
   e-book manager) passes, and "calibre" is still flagged.
   - Rules in `gitlab_base` come from the `gitlab` repository. Propose the
     change there, and use an inline disable until it merges.
1. Never set a whole rule to `NO` in `.vale.ini` for one term. If a project
   already does that, report it as a `minor` finding, with the narrower fix.

## Report

- Interactive mode: show each proposed exception with the term, the hit count,
  two example sentences, and the source that proves the spelling.
- Auto mode: in the fix loop, add exceptions to the project's own vocabulary
  in a separate fix commit. Do not edit rules that come from another repository. For those, use
  an inline disable, and list the upstream change in the summary for the TW to
  decide. Vocabulary changes affect every page, so the summary always lists
  them.

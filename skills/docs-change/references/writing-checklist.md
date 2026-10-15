# Writing checklist (writer pre-flight)

Run this list on your own draft before you hand it to `docs-review`. It is a
writer's pre-flight, not a review: fix what it finds, then let the read-only
reviewers judge the result. The items are the rules GitLab technical writers
flag most often in real reviews, most frequent first. Each is phrased as a
check you can answer yes or no.

Contents:

- [Facts and scope](#facts-and-scope)
- [Structure](#structure)
- [Links](#links)
- [Words](#words)

## Facts and scope

1. Is every technical claim (flag names, defaults, permissions, commands,
   UI labels) backed by code, tests, CLI help, or the product UI? If not,
   list it as a question for a subject matter expert instead of guessing.
2. Is every term clear to a first-time reader, with no ambiguous "it", "this",
   or "difference" and no assumed knowledge of other features?
3. Is each fact stated once? Delete repeats within the page and content that
   another page already owns; link to it.
4. Did you leave availability, tier, subscription, billing, credit, and price
   details to their single source of truth (the details block and the billing
   page), with no inline numbers?
5. Does the text describe only the current state, with no "not yet",
   "coming soon", "planned", or "will be available"?
6. Did you match the UI exactly: button and field names, and steps that exist?
7. Did you list defaults when you tell readers to keep them, and mark only
   truly optional steps as `Optional.`?

## Structure

8. Does each page lead with why, then the task, then examples? Does the task
   come before examples and billing notes?
9. Is each topic one type: concept (noun title), task (verb title),
   reference, or troubleshooting? No FAQ, no question headings.
10. Are troubleshooting titles symptoms or `Error:` messages, with cause and
    resolution in the body, and last on the page?
11. Are task steps one action each, location before action, with the
    current UI navigation phrasing (for example `1. In the upper-right corner, select **Admin**.`)?
12. Could a new page be a section on an existing page instead?

## Links

13. Does every link work after your change: relative links inside the
    project, absolute `https://docs.gitlab.com/...` URLs to other projects'
    docs, no links to MR diffs or internal-only tools?
14. Did you update every inbound link to a renamed heading or moved page?
15. Is the same URL linked at most once per section, with at most one link per task?

## Words

16. Did you avoid jargon, idioms, and sales language (for example
    "blast radius", "ship", "out of the box", "under the hood")?

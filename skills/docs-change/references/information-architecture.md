# Information architecture: where content goes

Contents:

- [Page roles](#page-roles)
- [Placement rules](#placement-rules)
- [Landing and overview pages with cards](#landing-and-overview-pages-with-cards)
- [Secondary concepts get less space](#secondary-concepts-get-less-space)

## Page roles

Each page has one job. Pick the role first, then write only what the role needs.

| Role | Job | Contains | Never contains |
|---|---|---|---|
| Overview (`_index.md` of a feature) | Say what the feature is for and route readers | One value sentence, cards to the main pages, a short "what you can do" table that links to use cases or tasks | Procedures, prerequisites, long comparisons |
| Get started / quickstart | Get a new user to a first success | Prerequisites, then numbered steps, one action per step, each with the output to expect | Concepts beyond one sentence, alternatives, reference tables |
| Concept | Explain what something is and why it matters | A noun title, a few paragraphs or a diagram | How-to steps, links to every related task |
| Task | Do one thing | Verb title, intro, `Prerequisites:`, `To <do X>:`, ordered steps, result | Background that belongs in a concept |
| Reference | Look up facts | Tables or lists: settings, commands, limits | Narrative, steps |
| Troubleshooting | Fix a symptom | `Error:` or symptom titles, cause, resolution; last on the page or its own page | Feature explanations |
| Tutorial | Learn by doing a full scenario | `Tutorial:` title, sequential H2 tasks | Availability details |

Rules: [topic types](https://docs.gitlab.com/development/documentation/topic_types/),
[get started](https://docs.gitlab.com/development/documentation/topic_types/get_started/),
[top-level pages](https://docs.gitlab.com/development/documentation/topic_types/top_level_page/).

## Placement rules

- Prefer a section on an existing page over a new page. Do not create a page
  for one concept, term, or step when a page for it exists.
- Put content in the audience's folder: user tasks in user docs, instance
  settings in administration docs, API details in API docs.
- Link to the single source of truth for availability, pricing, billing,
  limits, and supported versions. Do not restate them.
- Each new page needs a nav entry (in docs-gitlab-com) and a `description`
  in its front matter. New file names use dashes and lowercase; a directory
  starts with `_index.md`.

## Landing and overview pages with cards

The cards shortcode builds cards from a list:

```markdown
{{< cards >}}

- [Quickstart](quickstart.md)
- [Configure the runner](configure.md)

{{< /cards >}}
```

- The card title is the link text. The card description is the target page's
  front matter `description`, so a bad description shows up on the overview.
  Write each `description` as one short sentence that starts with a verb.
- Links to redirect stubs, missing pages, or pages without a title are dropped
  without an error. After any move, compare rendered cards with the source
  list (`docs-preview` does this).
- External links take a description in the link title: `[Name](https://example.com "Description")`.
- Group cards by what the reader wants next ("Get started", "Connect",
  "Reference"), and keep each group small.

## Secondary concepts get less space

Structure the docs around what the reader does, not around how the product is
built.

- If readers do not choose between two modes or components, do not organize
  the docs around them. One sentence on the overview and one compact table on
  the concept page is enough.
- One set of topics, not two parallel trees per mode. Where modes differ,
  say so inside the topic, in a table row or a sentence.
- Cut comparison tables to the rows that change a reader's decision.
- A table that another page owns (supported tools, settings) lives on that
  page; link to it.

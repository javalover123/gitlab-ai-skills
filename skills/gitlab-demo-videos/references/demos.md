# Demos shipped in the kit (GitLab.com, fictional Acme Corp)

Each is in `app/demos/<slug>/` with a narration script in `narration/scripts/<slug>.json`, except `shell-smoke`
(a silent smoke test of the shared shell). Rebuild any of them with `node harness/narrated.mjs <slug>`.
Lengths are from the first builds, in September 2026.

These demos are examples and templates. They were written against GitLab 19.4; their titles and version captions
take the version from `gl-src.pin` (see `GITLAB_VERSION` below), but the narration describes 19.4 as it was
understood then. Before you publish a re-recording, check every spoken claim against the current docs: defaults,
limits, prices and model names change between releases.

| slug | video | audience | length | cues |
|---|---|---|---|---|
| `credits-dashboard` | Your GitLab Credits usage (profile > GitLab Credits) | any user | 0:52 | 8 |
| `credit-caps` | Set credit caps and unblock a user (flat cap, per-user override) | group Owner | 1:11 | 11 |
| `shell-smoke` | group settings form + flash, project settings, AI > Triggers via sidebar, admin panel | test only | - | - |

These three cover the patterns a new demo needs:

- Vue app with its own Apollo client, profile panel: `credits-dashboard` (`entry_credits.js` uses
  `createMockApolloClient`), reference scenario + script for narration.
- GitLab's default client + `mockBackend`, with state that survives a page change (`demoState`): `credit-caps`
  (`mocks.js`: a save on one page changes what the next page shows), `shell-smoke/entry_automate.js`.
- HAML settings form, full-page post answered by `rest.mjs`, flash after redirect: `shell-smoke`.
- Admin area sidebar (Self-Managed and Dedicated): `shell-smoke` (`panel: 'admin'` in `pages.mjs`).
- Smooth scrolling inside GitLab's scroll container: `smoothScrollTo()` in `credit-caps/scenario.mjs`.
- Version in titles and captions: `GITLAB_VERSION` from `app/src/shell/gitlab_version.mjs`, as
  `credit-caps/scenario.mjs` uses it. Never type a version number into a caption.
- Several demos sharing one set of pages: put the page builder in one demo (for example `shared.mjs`), import it
  from the other with `../<slug>/shared.mjs`, and point `entry` at `../<slug>/<file>`.
- Illustrative values (model names, prices): show them on screen only, keep them out of the voiceover, and say
  so in the script's `notes`.

## More examples (GitLab team members)

Six more demos (group GitLab Credits dashboard, model selection, flow triggers, Code Review Flow, GitLab Duo
availability, AI governance) are in the
[demo video library](https://gitlab.com/gitlab-com/customer-success/cx-engineering/cx-portfolio-and-services/customer-journeys/-/tree/main/Field-Resources/Demo-Videos).
It's a GitLab-internal project: you need access to the customer-journeys project. To use one, copy its
`app/demos/<slug>/` and `narration/scripts/<slug>.json` into your kit. Nothing in this skill depends on them.

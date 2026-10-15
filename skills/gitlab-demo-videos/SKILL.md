---
name: gitlab-demo-videos
description: "Make a narrated walkthrough or demo video (MP4 with voiceover and captions) of a GitLab UI flow with synthetic data and no GitLab instance. Pages are built from GitLab's own frontend source at a pinned release tag, clicked through with Playwright, and voiced with a local text-to-speech model. Use when asked for a GitLab demo video, feature walkthrough, how-to or enablement video, a screen recording with fake data, or a voiceover for a GitLab feature, including GitLab.com-only settings and dashboards that a local instance cannot show. Not for screens outside the gitlab-org/gitlab codebase (such as the Customers Portal) or for real customer data."
version: 1.0.0
license: MIT
category: Documentation
metadata:
  audience: general
  workflow: demo-videos
---

# GitLab demo videos

Produces short narrated walkthroughs of GitLab features without recording a real instance. Pages come from
GitLab's own frontend source at the tag in `kit/gl-src.pin` (real sidebar, top bar and Vue apps, bundled with
Vite), filled with synthetic data (fictional org Acme Corp, user Alex Rivera) from an in-browser mock backend.
Playwright moves a visible cursor through a `scenario.mjs` at 1920x1080, and local Kokoro TTS reads the
narration. The scenario's `say(id)` calls pace the clicks to the voiceover.

## When to use

Use when someone wants a GitLab feature shown step by step: customer enablement, support how-tos, SA demo
prep, release walkthroughs, or dashboards that need believable fake data. It is a good fit for GitLab.com-only
pages (billing, GitLab Credits, GitLab Duo settings), which return 404 on a local GitLab.

It is not a fit for screens outside `gitlab-org/gitlab`, such as the Customers Portal (say "in the Customers
Portal" in the narration instead), or for anything that must show a real customer, instance or person.
A person must review every narrated claim before the video goes out.

## Set up (once per machine or cloud session)

```sh
bash <skill-dir>/scripts/setup.sh <work-dir>/gitlab-demo   # 5-10 min the first time, idempotent
cd <work-dir>/gitlab-demo
node harness/narrated.mjs credit-caps                      # smoke test, about 2-3 min
```

It makes a sparse, blobless checkout of `gitlab-org/gitlab` at 19.4 (never a full clone), installs npm deps,
compiles GitLab's CSS, and installs ffmpeg and Kokoro. Add `--gitlab-tag v18.11.2-ee` (or `master`) for another
GitLab version. Cloud vs. local, and what to check on another version: [references/setup.md](references/setup.md).

## Make a video

```sh
node harness/narrated.mjs <slug>    # cue lengths -> paced recording -> voiceover mux + captions
```

Outputs land in `out/<slug>/`: `<slug>-narrated.mp4` (the deliverable), `<slug>.mp4` (silent),
`<slug>.srt`/`.vtt`, `<slug>-<mark>.png` stills and `<slug>-preview.gif`. The kit ships two example demos and a
smoke test, listed in [references/demos.md](references/demos.md); copy the closest one when starting a new demo.

## Add a new demo

Read [references/harness.md](references/harness.md) first (page fields, sidebar ids, mocking, cursor API).

1. **Find the real UI in `gl-src`**: controller, view (`{ee/,}app/views/**.haml`), `#js-...` mount point, the
   Vue app's `index.js`, mock data in `ee/spec/frontend/**/mock_data.js`, behaviour in `gl-src/doc/**`.
2. **`app/demos/<slug>/pages.mjs`**: one entry per page (`route`, `group`/`project`, `activeMenuId`, `title`,
   `crumbs`, `bodyPage`, `content`, `entry`). **`entry_*.js`** starts with `import '@demo/src/shell/boot';`,
   registers mocks, then calls GitLab's real init function unmodified.
3. **Mocks**: `mockBackend.graphql({...})` / `mockBackend.rest({...})`, or `createMockApolloClient`. Keep
   in-memory state so a save changes the next query. Synthetic data only.
4. **`scenario.mjs`**: click through the real sidebar, `say('<cue>')` when a line starts, `await settle()`
   before the next one, `mark('<name>')` for stills. Version text comes from `GITLAB_VERSION`, never a typed number.
5. **`narration/scripts/<slug>.json`**: one cue per screen, in scenario order. Format, voices and
   pronunciation: [references/narration.md](references/narration.md).
6. `node harness/check.mjs <slug>` until there are no console errors or unmocked calls, then
   `node harness/narrated.mjs <slug>`.

## Verify before handing a video over

A video that rendered can still be silent, stretched, or showing the wrong screen:

```sh
tools/ffmpeg -i out/<slug>/<slug>-narrated.mp4 2>&1 | grep -E "Duration|Stream"   # 1 h264 1920x1080 + 1 aac
tools/ffmpeg -i out/<slug>/<slug>-narrated.mp4 -map 0:a -af volumedetect -f null - 2>&1 | grep mean_volume  # about -18 dB, not -91
jq .warnings narration/work/<slug>/timing.json                                    # must be []
tools/ffmpeg -ss <cue start + 1.5> -i out/<slug>/<slug>-narrated.mp4 -frames:v 1 out/<slug>/check-frame.png
```

Cue starts are in `out/<slug>/cues.json`. Check that each frame and `mark()` still shows what its line says
(right page, data loaded, no error toast). In the hand-off, list lines you could not confirm in source or docs
as "needs human review", and ask the person to listen for misread names and acronyms.

## Lessons that save re-records (full list: [references/lessons.md](references/lessons.md))

- Pace clicks to the narration with `say()`/`settle()`; never hand-time cue offsets.
- One cue per screen. Describe a page only once it is visible.
- After a save that reloads the same URL, wait for new content (flash, toast, new value), not network idle.
- Record at most 2 demos at a time; a busy machine stretches videos with silent gaps.
- Fix how a word is spoken with the script's `pronounce` map; captions keep the original text.
- Keep illustrative numbers and model names out of the voiceover.

## Keeping changes

In an ephemeral cloud session the restored work dir is lost when the session ends. Copy new or changed demo
sources back into this skill's `kit/` (same relative paths; never `node_modules`, `app/.build`, `gl-src`,
`narration/models`, `narration/.venv`, `narration/work`, `out` or `tools`), bump `version`, and open a merge
request. Deliver the finished MP4 and caption files wherever the person wants them.

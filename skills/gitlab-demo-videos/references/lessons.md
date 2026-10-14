# Lessons learned (from building the first 8 demos)

Each item is something that went wrong at least once. The kit already handles the ones marked (handled);
the rest are habits to keep when writing scenarios and scripts.

## Contents
1. Recording
2. Scenario pacing and narration
3. Content and accuracy
4. Environment

## 1. Recording

- **CDP screencast frames must be sorted by timestamp** (handled in `harness/record.mjs`). `Page.screencastFrame`
  events arrive out of order around navigations; encoding them in arrival order gives visible back-jumps. The
  recorder sorts and dedupes by capture timestamp and encodes with the ffmpeg concat demuxer using per-frame
  durations. If you ever write another recorder, keep that, or you will get a jittery video.
- **Load stretches videos.** On a 4 vCPU cloud container, recording 4+ demos in parallel starved Chromium: the screencast
  delivered few frames, waits took longer than the narration expected, and the narrated result had silent gaps
  and frozen stretches. Record at most 2 at a time, and check `uptime` first; if the load average is above ~3,
  wait. Building (`vite build`) in parallel is fine; recording is the sensitive step.
- `mark()` stills are taken after the state has painted, and the recorder keeps capturing until a frame newer
  than the last action has arrived, so the tail is never cut (handled).
- Chromium's paint holding keeps the previous page visible until the new page's Vue shell mounts, so a slow local
  bundle does not flash unstyled HTML (handled in the shell). If you see a white flash, the page probably threw
  before mounting: run `node harness/check.mjs <slug>` and read the console errors.

## 2. Scenario pacing and narration

- **Pace clicks to the narration with `say()` / `settle()`.** The recording is paced by the voiceover, never
  the other way round. `say(id)` starts a line; `settle()` waits until it has been spoken (+0.3 s). Every `say()`
  needs a `settle()` (or an awaited `say`) before the next one; otherwise the recorder warns and queues the line.
  Hand-timed `start` offsets drifted every time the UI changed; `say()` never drifts.
- **Split narration cues around page loads.** A single long line that spans a click-and-navigate ends up talking
  about a page that is not on screen yet (or already gone). Make one cue per screen: the line that sets up the
  click ends, the navigation happens, the next cue describes the new page once its content is visible.
- **Wait for real page content, not network idle, after a save that reloads the same URL.** A form post that
  redirects back to the same path makes `page.waitForURL(sameGlob)` resolve immediately and `waitForIdle()` can
  resolve before the reload starts. Wait for something that only exists after the reload: the flash text
  (`page.getByText("... was successfully updated")`), a toast, or a badge with the new value. Likewise after any
  click that navigates, wait for the *new* URL with a predicate that the old URL does not match.
- Keep cursor motion readable: `cursor.moveTo()` to the target while the line names it, a short `pause()`, then
  `cursor.click()`. Around 60-75 s per video with 8-12 cues worked well for customer enablement.
- Voice: Kokoro `af_heart` at speed 1.0 by default; keep one voice across a series. Write the cue text the way a
  person says it: short sentences, UI labels exactly as shown on screen ("select Save", not "click the save
  button"), following the [GitLab documentation style](https://docs.gitlab.com/development/documentation/styleguide/word_list/).
- **Acronyms and product names get misread.** Kokoro may read an acronym letter by letter when people say it as
  a word, or the other way round. Fix the spoken form with the script's `pronounce` map (or a cue's `spoken`
  text) so the captions keep the real spelling. Ask the requester how their team says each acronym.
- Verify every narrated build: `timing.json` `warnings` must be empty, the audio mean volume is around -18 dB
  (not -91 dB = silence), and a frame grabbed mid-cue shows what that line talks about.

## 3. Content and accuracy

- **GitLab.com-only billing pages 404 in a real local GitLab** (GDK / Omnibus / docker, even with EE license):
  GitLab Credits dashboard, credit caps, usage quotas billing tabs, and most GitLab Duo and Duo Agent Platform SaaS settings are gated on
  `Gitlab::Saas` + subscription data that a local instance does not have. That is why the kit builds pages from
  the real Vue/HAML source at a release tag with a mocked backend instead of screen-recording a running GitLab.
- **The Customers Portal (customers.gitlab.com) is not in gitlab-org/gitlab.** Purchase, seat add-on and invoice
  flows cannot be rebuilt from source here; show the in-product side and say "in the Customers Portal" in the
  narration, or leave that step out.
- **Mark UI-unverified claims for human review.** The source tells you what the UI can render, not always what a
  given customer will see (feature flags, plan, rollout). When a line or a screen depends on something you could
  not confirm in source or `gl-src/doc/**` (a flag default, a price, a model name, a limit), note it in the
  script's `notes` field and in your hand-off message as "needs review", and keep numbers and model names out of
  the voiceover if they are illustrative. Record with the flag on by default unless told otherwise.
- **Synthetic data only.** Fictional org **Acme Corp** (`acme-corp`, projects like `acme-corp/checkout-service`),
  signed-in user **Alex Rivera** (`@arivera`), other people with plain fictional names (Priya Natarajan, ...).
  Never put a real customer, employee, or instance in a video. These live in `app/src/shell/contexts.mjs` and the
  demos' `data.js`.
- **Fixed clock.** Every scenario sets `meta.demoTime` (+ `timezoneId`); `harness/fake_date.js` shifts `Date` so
  "3 days ago", chart ranges and billing periods are stable between re-recordings. Use dates consistent with the
  data (current billing month, etc.).

## 4. Environment

- **espeak-ng data path must be under ~160 chars.** espeak-ng silently ignores longer data paths and Kokoro
  then fails or produces garbage phonemes. Session scratch paths are often longer, so the data is copied to
  `~/.cache/espeak-ng-data` (handled in `narration/setup.sh` and `narrate.py`).
- Cloud sandboxes often block huggingface.co and public CDNs (jsdelivr, unpkg). Hence the Kokoro model files
  come from the `thewh1teagle/kokoro-onnx` GitHub release, and nothing in a page may load from a CDN.
- When Playwright and Chromium are preinstalled (common in cloud sessions), use them and do not run
  `playwright install`; `harness/browser.mjs` finds the global install. Locally, setup installs them.
- Never do a full clone of gitlab-org/gitlab (multi-GB). The kit uses `--filter=blob:none --depth 1` + a non-cone
  sparse checkout (~220 MB). Commands that walk the whole tree (`git grep`, `git log -p`, `git status` after a
  `sparse-checkout disable`) trigger fetching every blob.
- Cloud containers are ephemeral. Anything you want to keep (new demos, script edits, new sparse paths, new npm
  deps) must be copied back into the skill's `kit/` and contributed in a merge request, or delivered as output
  files.

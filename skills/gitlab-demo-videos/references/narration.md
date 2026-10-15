# Narration reference (local neural TTS)

Adds a voiceover track and captions to a finished demo video. Everything runs locally:
no TTS API, no account. The video stream is copied bit for bit, so the picture is never re-encoded.

```
narration/
  setup.sh                    one-time install: Kokoro (default) + optional Piper
  narrate.py                  the step
  scripts/<slug>.json         narration script: voice + cues
  models/                     kokoro-v1.0[.int8|.fp16].onnx, voices-v1.0.bin, piper/*.onnx (setup.sh)
  work/<slug>/                per-cue wavs, voice-raw.wav, voice.wav (normalized), timing.json
```

## Run

```sh
narration/setup.sh                                             # once (scripts/setup.sh runs it)
node harness/narrated.mjs credits-dashboard                  # the normal way: durations -> paced record -> mux
narration/.venv/bin/python narration/narrate.py credits-dashboard   # step 3 alone (re-mux an existing recording)
#  -> out/credits-dashboard/credits-dashboard-narrated.mp4   (H.264 copied + AAC 48 kHz; no subtitle track)
#     out/credits-dashboard/credits-dashboard.srt / .vtt       (sidecar captions)
#     narration/work/credits-dashboard/timing.json            (placement, overruns, warnings)

# audition a voice on the first cues (~14 s mp3)
narration/.venv/bin/python narration/narrate.py credits-dashboard --voice am_michael --sample out/narration-samples/x.mp3
narration/.venv/bin/python narration/narrate.py credits-dashboard --engine piper --voice en-us-lessac-medium --sample y.mp3
```

Options: `--voice`, `--speed` (Kokoro 0.5-2.0), `--engine kokoro|piper`, `--out`, `--embed-subs` (also add a
non-default mov_text track; off by default, captions are sidecar files), `--durations-only` (writes
`out/<slug>/durations.json`, copied to `work/<slug>/`).

## Script format

```json
{ "engine": "kokoro", "voice": "af_heart", "speed": 1.0,
  "pronounce": { "SAST": "sast", "DAST": "dast" },
  "cues": [
    { "id": "intro",  "text": "Here's how to check your own GitLab Credits usage." },
    { "id": "totals", "text": "..." } ] }
```

`text` is what the captions show. By default it is also what the voice reads.

## Pronunciation

Kokoro reads most text well, but it guesses at acronyms and product names. Some come out letter by letter
when your team says them as a word, and some the other way round. Fix the spoken form, not the captions:

- `"pronounce"` at the top of the script: whole-word, case-sensitive replacements applied to every cue's
  spoken text, for example `{ "DAP": "dap", "CARR": "C.A.R.R.", "Cowork": "Co-work" }`. Dotted letters
  (`C.A.R.R.`) usually come out letter by letter; a lower-case word (`dap`) usually comes out as one word.
- `"pronounce"` on a cue: merged over the script-level map for that cue only.
- `"spoken"` on a cue: replaces that cue's spoken text entirely, for anything a word map can't fix.

Ask the team how they say each acronym before recording a series, and keep the map the same across videos.
After a change, re-run `node harness/narrated.mjs <slug>`: cue lengths change, so the recording is re-paced.

Cue times, in priority order: `out/<slug>/cues.json` written by a recording whose scenario calls `say(id)`
(the convention, see "Narration" in [harness.md](harness.md)), else `start` (seconds into the video), else `scene`
(a `mark()` from `out/<slug>/marks.json`) plus optional `offset`. A cue with none of these is an error.
A cue may override `voice` / `speed`.

What the step does:
1. Synthesizes each cue, trims leading/trailing silence.
2. Places cues at their start time. If a cue would start before the previous one ends (plus 0.25 s),
   it gets pushed later and a warning is logged. A cue that runs past the next cue's planned start is
   reported as an overrun (`timing.json` → `warnings`, `cues[].overrun`). Nothing overlaps, and
   nothing is cut unless it runs past the end of the video (also reported).
3. Mixes to one mono track, runs two-pass `loudnorm` to -16 LUFS integrated (-1.5 dBTP), 48 kHz.
4. Writes SRT/VTT: each cue is split at sentence or clause boundaries into captions of at most 2x42 chars,
   timed in proportion to their length within the cue's actual audio span.
5. Muxes `-c:v copy` + AAC 160k (+ soft subtitles with `--embed-subs`), trimmed to the video duration.

## Engines and voices

- **Kokoro-82M** (`kokoro-onnx` 0.6.1, onnxruntime CPU). Default. About 14 s to narrate 49 s of video.
  Good voices: `af_heart` (default, warm US female), `af_bella`, `am_michael` (US male, natural pace on long
  scripts), `bm_george` (UK male). Keep one voice across a series. `KOKORO_MODEL=int8` uses the 92 MB
  quantized model (set it for both `narration/setup.sh` and the run); quality is close to the full model.
  All 54 voices: `python -c "from kokoro_onnx import Kokoro; ..."` → `get_voices()`.
- **Piper** (`piper-tts` 1.8.0), voice `en-us-lessac-medium`. Works, but sounds flatter and more
  "TTS-like" than Kokoro. Kept as a fallback.
- Gotcha handled in `narrate.py`: espeak-ng (used for phonemes) ignores data paths longer than about
  160 chars, and session scratch paths are often longer than that. So the bundled `espeak-ng-data` is copied once
  to `~/.cache/espeak-ng-data` (setup.sh and narrate.py both do it). Symptom if it is missing/broken: phonemizer
  errors about `phontab` or an espeak data path.

Network: the kit needs only github.com release assets and PyPI. Many cloud sandboxes block huggingface.co,
which rules out newer Piper voices, Kokoro .pth weights and most voice-cloning models there. Voice cloning
(narrating in a real person's voice) is out of scope for this skill: it needs that person's consent, a clean
reference recording, and a license review of the cloning model.

## Checking audio you cannot hear

Agents usually cannot listen to the result, so check it by numbers and say so in the hand-off:

- mean volume about -18 dB with `volumedetect` (around -91 dB means silence);
- `timing.json` `warnings` empty (no overlaps, overruns or truncation);
- cue lengths in `durations.json` look plausible for the text (about 2.5-3 words per second);
- ask the person to listen for names, acronyms and numbers, and fix them with `pronounce`.

## Sharing the files

Chat tools often cap uploads (Slack, for example, may reject large files). The narrated MP4 is usually a few
MB per minute. If it is too big, re-encode a sharing copy and keep the original for storage:

```sh
tools/ffmpeg -i out/<slug>/<slug>-narrated.mp4 -c:v libx264 -crf 26 -preset slow -c:a aac -b:a 96k out/<slug>/<slug>-share.mp4
```

## Pacing video to narration (implemented)

The recording is paced by the narration, not the other way round:

1. `narrate.py <slug> --durations-only` writes `out/<slug>/durations.json` (`{ "intro": 2.63, ... }`).
2. `harness/record.mjs` loads it and gives the scenario `say(id)` (records the cue's start relative to
   video t=0 and resolves when its audio ends) and `settle(minMs)` (waits for the current line + 0.3 s).
   It writes `out/<slug>/cues.json` (`{ id: seconds }`, same shape as `marks.json`) and deletes any stale
   one at the start of every recording.
3. `narrate.py <slug>` places each line at its `cues.json` time. Every cue fits its scene by construction;
   changing the text only needs a re-run of `node harness/narrated.mjs <slug>`, no hand re-timing.

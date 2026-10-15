#!/usr/bin/env python3
"""Add local neural-TTS voiceover + captions to a recorded demo video.

  narration/.venv/bin/python narration/narrate.py <slug> [script.json] [options]

Reads   out/<slug>/<slug>.mp4, out/<slug>/cues.json (cue start times from a say()-paced recording, wins),
        out/<slug>/marks.json (for cues that use a scene id), narration/scripts/<slug>.json (default script path)
Writes  out/<slug>/<slug>-narrated.mp4 (video stream copied untouched + AAC voiceover)
        out/<slug>/<slug>.srt, out/<slug>/<slug>.vtt (sidecar captions; --embed-subs also adds a mov_text track)
        narration/work/<slug>/  per-cue wavs, voice.wav (mixed + normalized), timing.json

Script JSON: {"engine": "kokoro"|"piper", "voice": "af_heart", "speed": 1.0,
              "cues": [{"id", "text"} (placed by say(id) -> cues.json) | {"id", "text", "start": seconds}
                       | {"id", "text", "scene": "<mark>", "offset": s}]}
Per-cue "voice"/"speed" override the defaults.

Pronunciation (spoken text only; captions always show "text"):
  script-level "pronounce": {"DAP": "dap", "CARR": "C.A.R.R."}  whole-word, case-sensitive replacements
  per-cue "pronounce": {...}                                    merged over the script-level map
  per-cue "spoken": "..."                                       replaces the spoken text of that cue entirely
Kokoro model: models/kokoro-v1.0.onnx, or the file named by $KOKORO_MODEL (int8 | fp16 | a file name).

--sample OUT.mp3 [--sample-seconds 14]: skip the video, just render the first cues back to back
(voice audition clip).
--durations-only: synthesize and write out/<slug>/durations.json (+ narration/work/<slug>/durations.json)
for recorder pacing (harness/record.mjs say()/settle()).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FFMPEG = str(ROOT / 'tools' / 'ffmpeg')
SR = 24000            # Kokoro native rate; Piper output is resampled to this
MIN_GAP = 0.25        # silence enforced between cues (s)
LUFS, TP, LRA = -16.0, -1.5, 11.0


# ---------------------------------------------------------------- TTS engines
_kokoro = None

def _espeak_data_dir():
    # espeak-ng silently ignores data paths longer than ~160 chars and falls back to the
    # (non-existent) compile-time path, and phonemizer resolves symlinks - so keep a real copy
    # at a short path.
    import espeakng_loader
    short = Path.home() / '.cache' / 'espeak-ng-data'
    if not (short / 'phontab').exists():
        shutil.copytree(espeakng_loader.get_data_path(), short, dirs_exist_ok=True)
    return str(short)

def tts_kokoro(text, voice, speed):
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro, EspeakConfig
        _kokoro = Kokoro(str(kokoro_model_path()), str(HERE / 'models' / 'voices-v1.0.bin'),
                         espeak_config=EspeakConfig(data_path=_espeak_data_dir()))
    samples, sr = _kokoro.create(text, voice=voice, speed=speed, lang='en-us')
    assert sr == SR
    return np.asarray(samples, dtype=np.float32)

def tts_piper(text, voice, speed):
    model = HERE / 'models' / 'piper' / f'{voice}.onnx'
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / 'p.wav'
        subprocess.run([str(HERE / '.venv-piper' / 'bin' / 'piper'), '-m', str(model), '-f', str(raw),
                        '--length-scale', str(1.0 / speed)], input=text.encode(), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = Path(td) / 'r.wav'
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', str(raw), '-ar', str(SR), '-ac', '1', str(out)], check=True)
        return read_wav(out)

ENGINES = {'kokoro': tts_kokoro, 'piper': tts_piper}


def kokoro_model_path():
    """models/kokoro-v1.0.onnx unless $KOKORO_MODEL picks the int8/fp16 file (or names one); else any present."""
    choice = os.environ.get('KOKORO_MODEL', '')
    names = {'': 'kokoro-v1.0.onnx', 'int8': 'kokoro-v1.0.int8.onnx', 'fp16': 'kokoro-v1.0.fp16.onnx'}
    preferred = HERE / 'models' / names.get(choice, choice)
    if preferred.exists() or choice:
        return preferred
    for name in names.values():
        if (HERE / 'models' / name).exists():
            return HERE / 'models' / name
    return preferred


def spoken_text(cue, script):
    """What the TTS engine reads for a cue. Captions keep cue['text'].

    TTS models misread some acronyms and product names (reading "DAP" letter by letter, for example).
    Fix them with a "pronounce" map instead of changing the caption text."""
    if cue.get('spoken'):
        return cue['spoken']
    text = cue['text']
    subs = {**script.get('pronounce', {}), **cue.get('pronounce', {})}
    for word in sorted(subs, key=len, reverse=True):
        text = re.sub(r'(?<![\w-])' + re.escape(word) + r'(?![\w-])', lambda _m, r=subs[word]: r, text)
    return text


# ---------------------------------------------------------------- audio helpers
def read_wav(p):
    with wave.open(str(p)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a

def write_wav(p, a):
    a = np.clip(a, -1, 1)
    with wave.open(str(p), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())

def trim(a, thresh=0.004, pad=0.04):
    idx = np.flatnonzero(np.abs(a) > thresh)
    if not len(idx):
        return a
    p = int(pad * SR)
    return a[max(0, idx[0] - p): idx[-1] + p]

def ff(*args, capture=False):
    r = subprocess.run([FFMPEG, '-hide_banner', '-nostats', *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return r.stderr if capture else None

def loudnorm(src, dst, extra_out=()):
    """Two-pass EBU R128 normalization to LUFS/TP/LRA."""
    err = ff('-i', str(src), '-af', f'loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:print_format=json', '-f', 'null', '-', capture=True)
    m = json.loads(err[err.rindex('{'):err.rindex('}') + 1])
    af = (f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    ff('-y', '-i', str(src), '-af', af, '-ar', '48000', *extra_out, str(dst))
    return m

def duration(path):
    err = subprocess.run([FFMPEG, '-hide_banner', '-i', str(path)], stderr=subprocess.PIPE, text=True).stderr
    h, m, s = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------------------------------------------------------------- captions
def caption_chunks(text, maxlen=84):
    """Split a cue into caption-sized chunks at sentence, then clause boundaries."""
    parts = re.split(r'(?<=[.?!])\s+', text.strip())
    out = []
    for p in parts:
        n = -(-len(p) // maxlen)          # split long sentences into n roughly equal pieces
        while n > 1:
            target = len(p) // n
            spaces = [i for i, ch in enumerate(p) if ch == ' ' and i <= maxlen]
            commas = [i for i in spaces if p[i - 1] == ',' and abs(i - target) <= 12]
            cut = min(commas or spaces, key=lambda i: abs(i - target))
            out.append(p[:cut].strip()); p = p[cut:].strip(); n -= 1
        out.append(p)
    # merge tiny neighbours ("That's it." + next)
    merged = []
    for p in out:
        if merged and len(merged[-1]) + len(p) + 1 <= maxlen and (len(p) < 30 or len(merged[-1]) < 30):
            merged[-1] += ' ' + p
        else:
            merged.append(p)
    return merged

def wrap2(s, width=42):
    if len(s) <= width:
        return s
    mid = len(s) // 2
    spaces = [i for i, c in enumerate(s) if c == ' ']
    cut = min(spaces, key=lambda i: abs(i - mid))
    return s[:cut] + '\n' + s[cut + 1:]

def ts(t, sep):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02}{sep}{ms:03}'

def write_captions(placed, srt_path, vtt_path):
    entries = []
    for c in placed:
        chunks = caption_chunks(c['text'])
        total = sum(len(x) for x in chunks)
        t = c['start']
        for x in chunks:
            d = c['duration'] * len(x) / total
            entries.append((t, t + d, wrap2(x))); t += d
    srt = '\n'.join(f'{i}\n{ts(a, ",")} --> {ts(b, ",")}\n{txt}\n' for i, (a, b, txt) in enumerate(entries, 1))
    vtt = 'WEBVTT\n\n' + '\n'.join(f'{ts(a, ".")} --> {ts(b, ".")}\n{txt}\n' for a, b, txt in entries)
    Path(srt_path).write_text(srt); Path(vtt_path).write_text(vtt)
    return entries


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slug')
    ap.add_argument('script', nargs='?')
    ap.add_argument('--engine'); ap.add_argument('--voice'); ap.add_argument('--speed', type=float)
    ap.add_argument('--out')
    ap.add_argument('--sample', help='write an audition clip (mp3) instead of the narrated video')
    ap.add_argument('--sample-seconds', type=float, default=14)
    ap.add_argument('--durations-only', action='store_true', help='write work/<slug>/durations.json and exit')
    ap.add_argument('--embed-subs', action='store_true',
                    help='also embed the captions as a (non-default) mov_text track; default: sidecar .srt/.vtt only')
    ap.add_argument('--no-subs', action='store_true', help=argparse.SUPPRESS)  # old flag; embedding is now opt-in
    a = ap.parse_args()

    script = json.loads(Path(a.script or HERE / 'scripts' / f'{a.slug}.json').read_text())
    engine = a.engine or script.get('engine', 'kokoro')
    voice = a.voice or script.get('voice', 'af_heart')
    speed = a.speed or script.get('speed', 1.0)
    tts = ENGINES[engine]
    out_dir = ROOT / 'out' / a.slug
    work = HERE / 'work' / a.slug; (work / 'cues').mkdir(parents=True, exist_ok=True)

    if a.sample:
        clip, gap = [], np.zeros(int(0.45 * SR), np.float32)
        for c in script['cues']:
            clip += [trim(tts(spoken_text(c, script), c.get('voice', voice), c.get('speed', speed))), gap]
            if sum(len(x) for x in clip) / SR >= a.sample_seconds - 3:
                break
        tmp = work / f'sample-{engine}-{voice}.wav'; write_wav(tmp, np.concatenate(clip))
        Path(a.sample).parent.mkdir(parents=True, exist_ok=True)
        loudnorm(tmp, a.sample, ('-ac', '1', '-c:a', 'libmp3lame', '-b:a', '128k'))
        print(f'sample {a.sample} ({duration(a.sample):.1f}s)')
        return

    if a.durations_only:
        # For recorder-side pacing: {cue id: seconds of speech}; see README "Pacing video to narration".
        d = {c.get('id', str(i)): round(len(trim(tts(spoken_text(c, script), c.get('voice', voice), c.get('speed', speed)))) / SR, 3)
             for i, c in enumerate(script['cues'])}
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in (out_dir / 'durations.json', work / 'durations.json'):
            f.write_text(json.dumps(d, indent=2))
        print(json.dumps(d, indent=2))
        print('wrote', out_dir / 'durations.json')
        return

    video = out_dir / f'{a.slug}.mp4'
    vdur = duration(video)
    marks = json.loads((out_dir / 'marks.json').read_text()) if (out_dir / 'marks.json').exists() else {}
    # cue start times written by a narration-paced recording (out/<slug>/cues.json), if any
    recorded = json.loads((out_dir / 'cues.json').read_text()) if (out_dir / 'cues.json').exists() else {}
    if recorded:
        print('using recorded cue times from', out_dir / 'cues.json')
        ids = {c.get('id', str(i)) for i, c in enumerate(script['cues'])}
        for extra in sorted(set(recorded) - ids):
            print(f'WARN cues.json has "{extra}", which is not in the script (ignored)')

    # 1. synthesize
    cues = []
    for i, c in enumerate(script['cues']):
        cid = c.get('id', str(i))
        if cid in recorded:                      # recorder-paced run wins (see README)
            start = recorded[cid]
        elif 'start' in c:
            start = c['start']
        elif c.get('scene') in marks:
            start = marks[c['scene']] + c.get('offset', 0)
        else:
            sys.exit(f'cue "{cid}" has no time: not said in the recording (out/{a.slug}/cues.json), '
                     f'no "start", and no known "scene". Add say(\'{cid}\') to the scenario and re-record.')
        audio = trim(tts(spoken_text(c, script), c.get('voice', voice), c.get('speed', speed)))
        write_wav(work / 'cues' / f'{i:02}-{c.get("id", i)}.wav', audio)
        cues.append({'id': c.get('id', str(i)), 'text': c['text'], 'planned': start, 'audio': audio,
                     'duration': len(audio) / SR})
    cues.sort(key=lambda c: c['planned'])

    # 2. place: never overlap; report overruns of the scene gap (= time until the next planned cue)
    track = np.zeros(int(vdur * SR), np.float32)
    warnings, prev_end = [], 0.0
    for i, c in enumerate(cues):
        start = max(c['planned'], prev_end + MIN_GAP if i else c['planned'])
        if start > c['planned'] + 1e-3:
            warnings.append(f"{c['id']}: pushed {start - c['planned']:.2f}s later (previous cue overran)")
        nxt = cues[i + 1]['planned'] if i + 1 < len(cues) else vdur
        c['gap'] = nxt - c['planned']
        c['overrun'] = round(max(0.0, start + c['duration'] + MIN_GAP - nxt), 2)
        if c['overrun'] > 0:
            warnings.append(f"{c['id']}: {c['duration']:.2f}s of speech in a {c['gap']:.2f}s scene gap "
                            f"(overruns by {c['overrun']:.2f}s)")
        s0 = int(start * SR); a_ = c['audio'][: max(0, len(track) - s0)]
        if len(a_) < len(c['audio']):
            warnings.append(f"{c['id']}: TRUNCATED at video end ({len(c['audio']) - len(a_)} samples cut)")
        track[s0: s0 + len(a_)] += a_
        c['start'] = start; c['end'] = start + len(a_) / SR; c['duration'] = len(a_) / SR
        prev_end = c['end']

    raw = work / 'voice-raw.wav'; write_wav(raw, track)
    voice_wav = work / 'voice.wav'
    m = loudnorm(raw, voice_wav)

    # 3. captions + mux (video stream copied bit-for-bit)
    srt, vtt = out_dir / f'{a.slug}.srt', out_dir / f'{a.slug}.vtt'
    write_captions(cues, srt, vtt)
    dst = Path(a.out) if a.out else out_dir / f'{a.slug}-narrated.mp4'
    args = ['-y', '-i', str(video), '-i', str(voice_wav)]
    maps = ['-map', '0:v:0', '-map', '1:a:0']
    if a.embed_subs:
        args += ['-i', str(srt)]; maps += ['-map', '2:s:0', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng',
                                    '-disposition:s:0', '0']  # available, not forced on
    ff(*args, *maps, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
       '-metadata:s:a:0', 'language=eng', '-t', f'{vdur:.3f}', '-movflags', '+faststart', str(dst))

    report = {'engine': engine, 'voice': voice, 'speed': speed, 'video_duration': vdur,
              'input_loudness': m['input_i'], 'target_lufs': LUFS, 'output': str(dst), 'warnings': warnings,
              'cues': [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in c.items() if k != 'audio'}
                       for c in cues]}
    (work / 'timing.json').write_text(json.dumps(report, indent=2))
    for c in cues:
        print(f"{c['start']:6.2f}-{c['end']:6.2f}  ({c['duration']:.2f}s / gap {c['gap']:.2f}s)  {c['id']}")
    for w in warnings:
        print('WARN', w)
    print('wrote', dst, srt, vtt)


if __name__ == '__main__':
    main()

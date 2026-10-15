// Narrated demo in one command: cue lengths -> narration-paced recording -> voiceover mux + captions.
//
//   node harness/narrated.mjs <slug> [record.mjs options: --no-build --port=N --keep-raw ...]
//                                    [--voice=af_heart] [--speed=1.0] [--engine=kokoro]
//
// 1. narration/.venv/bin/python narration/narrate.py <slug> --durations-only  -> out/<slug>/durations.json
// 2. node harness/record.mjs <slug> ...  (say(id) marks each cue and waits for its audio length)
//                                        -> out/<slug>/<slug>.mp4 (silent), marks.json, cues.json, stills, gif
// 3. narration/.venv/bin/python narration/narrate.py <slug>
//                                        -> out/<slug>/<slug>-narrated.mp4 (video copied + AAC voiceover),
//                                           out/<slug>/<slug>.srt + .vtt (sidecar captions, not embedded)
// Script: narration/scripts/<slug>.json. Voice/speed/engine flags override the script for steps 1 and 3.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const ROOT = path.resolve(import.meta.dirname, '..');
const args = process.argv.slice(2);
const slug = args.find((a) => !a.startsWith('--'));
if (!slug) {
  console.error('usage: node harness/narrated.mjs <slug> [--no-build] [--port=N] [--keep-raw] [--voice=V] [--speed=S] [--engine=E]');
  process.exit(1);
}
const script = path.join(ROOT, 'narration', 'scripts', `${slug}.json`);
if (!fs.existsSync(script)) {
  console.error(`missing narration script ${path.relative(ROOT, script)}`);
  process.exit(1);
}
const PY = path.join(ROOT, 'narration', '.venv', 'bin', 'python');
const NARRATE = path.join(ROOT, 'narration', 'narrate.py');
const ttsKeys = ['voice', 'speed', 'engine'];
const ttsArgs = args.filter((a) => ttsKeys.some((k) => a.startsWith(`--${k}=`))).flatMap((a) => a.slice(2).split(/=(.*)/s, 2).map((x, i) => (i ? x : `--${x}`)));
const recArgs = args.filter((a) => a !== slug && !ttsKeys.some((k) => a.startsWith(`--${k}=`)));
const step = (name, cmd, cmdArgs) => {
  console.log(`\n=== ${name}: ${path.relative(ROOT, cmdArgs[0])} ${cmdArgs.slice(1).join(' ')}`);
  const t = Date.now();
  execFileSync(cmd, cmdArgs, { stdio: 'inherit', cwd: ROOT });
  console.log(`=== ${name} done in ${((Date.now() - t) / 1000).toFixed(1)}s`);
};

try {
  step('1/3 cue lengths', PY, [NARRATE, slug, ...ttsArgs, '--durations-only']);
  step('2/3 record', process.execPath, [path.join(ROOT, 'harness', 'record.mjs'), slug, ...recArgs]);
  if (!fs.existsSync(path.join(ROOT, 'out', slug, 'cues.json'))) {
    console.warn(`\nWARN the scenario never called say(); narrate.py will use the script's start/scene times`);
  }
  step('3/3 voiceover + captions', PY, [NARRATE, slug, ...ttsArgs]);
} catch (e) {
  console.error(`\nnarrated.mjs failed: ${e.message.split('\n')[0]}`);
  process.exit(1);
}
const out = path.join(ROOT, 'out', slug);
console.log(JSON.stringify({
  narrated: path.join(out, `${slug}-narrated.mp4`),
  silent: path.join(out, `${slug}.mp4`),
  captions: [path.join(out, `${slug}.srt`), path.join(out, `${slug}.vtt`)],
  cues: path.join(out, 'cues.json'),
  timing: path.join(ROOT, 'narration', 'work', slug, 'timing.json'),
}, null, 2));

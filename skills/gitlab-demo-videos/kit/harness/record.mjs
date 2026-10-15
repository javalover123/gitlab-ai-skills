// Records a demo scenario to MP4 (H.264) + GIF + PNG stills.
//
//   node harness/record.mjs <slug> [--no-build] [--capture=screencast|playwright] [--keep-raw] [--port=N] [--no-pace]
//
// Builds app/demos/<slug> into app/.build/<slug>/ (unless --no-build), serves it on a free port
// (or --port=N), runs app/demos/<slug>/scenario.mjs and writes out/<slug>/{<slug>.mp4, -preview.gif,
// -<mark>.png, marks.json} (+ cues.json when the scenario calls say()). Different slugs can record at the
// same time. For a narrated video use `node harness/narrated.mjs <slug>` (durations -> record -> mux).
//
// capture=screencast  grabs CDP screencast JPEG frames (q=95) with timestamps and encodes them
//                     directly -> sharp text, exact sync with mark(). (default)
// capture=playwright  uses Playwright's recordVideo (VP8 webm, then transcoded).
//
// Scenario API (default export async function run(ctx)):
//   ctx.page, ctx.cursor (click / moveTo / moveToPoint / clickPoint / point / sync), ctx.base (server URL)
//   ctx.pause(ms), ctx.mark(name)                     still at this instant -> out/<slug>/<slug>-<name>.png
//   ctx.waitForIdle()                                 network idle + fonts + 300ms
//   ctx.caption(text, { step })  / ctx.hideCaption()  subtle bottom caption (persists across navigations)
//   ctx.goto(route)                                   navigate within the demo (keeps cursor position)
//   ctx.type(locator, text, { delay })                human-ish typing into an input
// Narration pacing (cue ids from narration/scripts/<slug>.json, lengths from out/<slug>/durations.json):
//   ctx.say(id)        cue <id> starts NOW (video time -> out/<slug>/cues.json). Returns a promise that resolves
//                      when the line has been spoken: `await say(id)` = speak, then act;
//                      `say(id); ...actions...; await settle()` = act while speaking.
//   ctx.settle(minMs)  wait until the current line has been spoken (+ CUE_GAP), and at least minMs.
//   After run() returns the recorder settles automatically, so the last line is never cut off.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { startServer } from './serve.mjs';
import { Cursor } from './cursor.mjs';
import { buildDemo } from './build.mjs';
import { chromium, newDemoContext, W, H } from './browser.mjs';

const ROOT = path.resolve(import.meta.dirname, '..');
const APP = path.join(ROOT, 'app');
const FFMPEG = path.join(ROOT, 'tools/ffmpeg');
const args = process.argv.slice(2);
const demo = args.find((a) => !a.startsWith('--'));
if (!demo) {
  console.error('usage: node harness/record.mjs <slug> [--no-build] [--capture=screencast|playwright] [--keep-raw] [--port=N] [--no-pace]');
  process.exit(1);
}
const opt = (k, d) => (args.find((a) => a.startsWith(`--${k}=`)) || `=${d}`).split('=')[1];
const capture = opt('capture', 'screencast');
const FPS = 30;
const CUE_GAP = 300; // ms of silence kept between narration cues (narrate.py enforces >= 250 ms)
const TAIL = 700; // ms of picture kept after the last line has been spoken

const OUT = path.join(ROOT, 'out', demo);
const RAW = path.join(OUT, 'raw');
fs.rmSync(RAW, { recursive: true, force: true });
fs.mkdirSync(RAW, { recursive: true });
// cues.json belongs to one recording only; never let narrate.py pick up a stale one.
fs.rmSync(path.join(OUT, 'cues.json'), { force: true });

// --- narration cue lengths (for say/settle) ---
const readJson = (f) => (fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null);
const scriptFile = path.join(ROOT, 'narration', 'scripts', `${demo}.json`);
const script = readJson(scriptFile);
let durations = {};
let durationsSource = 'none';
if (script && !args.includes('--no-pace')) {
  const dFile = [path.join(OUT, 'durations.json'), path.join(ROOT, 'narration', 'work', demo, 'durations.json')].find((f) => fs.existsSync(f));
  if (dFile) {
    durations = readJson(dFile);
    durationsSource = path.relative(ROOT, dFile);
    if (fs.statSync(dFile).mtimeMs < fs.statSync(scriptFile).mtimeMs) {
      console.warn(`[narration] ${durationsSource} is older than the script - run: node harness/narrated.mjs ${demo}`);
    }
  }
  // Cues without a synthesized length: estimate (~15 chars/s) so pacing is roughly right anyway.
  for (const [i, c] of (script.cues || []).entries()) {
    const id = c.id ?? String(i);
    if (durations[id] == null) {
      durations[id] = Math.round((c.text.length / 15) * 1000) / 1000;
      if (durationsSource !== 'none') console.warn(`[narration] no synthesized length for cue "${id}", estimating ${durations[id]}s`);
      else durationsSource = 'estimated from script text (run narrate.py --durations-only for exact lengths)';
    }
  }
  console.log(`[narration] cue lengths: ${durationsSource}`);
}

if (!args.includes('--no-build')) {
  console.log('building...');
  await buildDemo(demo);
}

const { default: run, meta } = await import(path.join(APP, 'demos', demo, 'scenario.mjs'));
const server = await startServer({ slug: demo, port: Number(opt('port', 0)) });
const base = server.baseUrl;
console.log('serving on', base);

const browser = await chromium.launch({ args: ['--font-render-hinting=none', '--disable-lcd-text'] });
const context = await newDemoContext(browser, {
  demoTime: meta.demoTime,
  timezoneId: meta.timezoneId || 'UTC',
  cursorStart: meta.cursorStart || { x: 1400, y: 640 },
  recordVideo: capture === 'playwright' ? { dir: RAW, size: { width: W, height: H } } : undefined,
});

const page = await context.newPage();
page.on('pageerror', (e) => console.log('[pageerror]', e.message.slice(0, 200)));

// --- frame capture (screencast mode) ---
// Each frame keeps its capture timestamp (t, wall clock ms) and arrival time. Frames can arrive out of
// timestamp order (the screencast is restarted after every load, and frames queued by the old document land
// late), so they are sorted + deduped by t before encoding.
const frames = [];
let cdp;
const tVideo0 = Date.now();
if (capture === 'screencast') {
  cdp = await context.newCDPSession(page);
  let n = 0;
  cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    const file = path.join(RAW, `f${String(n++).padStart(6, '0')}.jpg`);
    fs.writeFileSync(file, Buffer.from(data, 'base64'));
    frames.push({ file, t: metadata.timestamp * 1000, arr: Date.now() });
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 95, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  // Screencast stops across cross-document navigations in some versions; restart on load.
  page.on('load', () => cdp.send('Page.startScreencast', { format: 'jpeg', quality: 95, maxWidth: W, maxHeight: H }).catch(() => {}));
}

// page.evaluate that survives a navigation in flight (retries once the new document has loaded).
async function safeEval(fn, arg) {
  for (let i = 0; i < 5; i += 1) {
    try {
      return await page.evaluate(fn, arg);
    } catch (e) {
      if (!/Execution context was destroyed|navigation/i.test(e.message)) throw e;
      await page.waitForLoadState('load').catch(() => {});
    }
  }
  return undefined;
}
// Resolves once the current DOM state has been painted (two animation frames).
const painted = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())))).catch(() => {});

const marks = {};
const pendingMarks = [];
const cueTimes = {};
let tStart = 0;
let speechUntil = 0; // wall-clock ms at which the current cue's audio ends
const cursor = new Cursor(page, meta.cursorStart);
const ctx = {
  page,
  cursor,
  base,
  pause: (ms) => page.waitForTimeout(ms),
  // Timestamped after the state at call time has been painted, so the still shows it. Non-blocking.
  mark: (name) => {
    const p = painted().then(() => {
      marks[name] = Date.now();
      console.log('mark', name);
    });
    pendingMarks.push(p);
    return p;
  },
  say: (id) => {
    if (!script) {
      console.warn(`[narration] say('${id}') but no narration/scripts/${demo}.json - ignored`);
      return Promise.resolve();
    }
    if (args.includes('--no-pace')) return Promise.resolve();
    if (durations[id] == null) throw new Error(`say('${id}'): no cue with id "${id}" in narration/scripts/${demo}.json`);
    if (id in cueTimes) console.warn(`[narration] cue "${id}" said twice; keeping the last start`);
    let now = Date.now();
    if (now < speechUntil + CUE_GAP) {
      console.warn(`[narration] say('${id}') ${((speechUntil + CUE_GAP - now) / 1000).toFixed(2)}s before the previous line ends - add settle() before it`);
      now = speechUntil + CUE_GAP; // narrate.py would push it the same way
    }
    cueTimes[id] = Math.round(now - tStart) / 1000;
    speechUntil = now + durations[id] * 1000;
    console.log(`say ${id} @${cueTimes[id].toFixed(2)}s (${durations[id]}s)`);
    return new Promise((r) => setTimeout(r, Math.max(0, speechUntil - Date.now())));
  },
  settle: async (minMs = 0) => {
    const wait = Math.max(minMs, speechUntil ? speechUntil + CUE_GAP - Date.now() : 0);
    if (wait > 0) await page.waitForTimeout(wait);
  },
  waitForIdle: async () => {
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
  },
  caption: (text, o = {}) => safeEval(([t, s]) => window.__demoCaption?.show(t, { step: s }), [text, o.step || '']),
  hideCaption: () => safeEval(() => window.__demoCaption?.hide()),
  goto: async (route) => {
    await page.goto(base + route);
    await ctx.waitForIdle();
    await cursor.sync();
  },
  type: async (locator, text, { delay = 55 } = {}) => {
    await locator.pressSequentially(text, { delay });
  },
};

await page.goto(base + meta.startRoute);
await ctx.waitForIdle();
await cursor.sync();
await page.waitForTimeout(400);
tStart = Date.now();
try {
  await run(ctx);
  // Let the last narration line finish, then hold the final picture briefly.
  if (speechUntil) await page.waitForTimeout(Math.max(0, speechUntil - Date.now()) + TAIL);
  await Promise.all(pendingMarks);
} catch (e) {
  const shot = path.join(OUT, 'error.png');
  await page.screenshot({ path: shot }).catch(() => {});
  console.error(`scenario failed at ${((Date.now() - tStart) / 1000).toFixed(1)}s: ${e.message}\nscreenshot: ${shot}`);
  await browser.close().catch(() => {});
  server.close();
  process.exit(1);
}
// Final state painted -> tEnd. Then keep nudging a 1px element until a frame captured after tEnd has
// arrived, so the tail of the video is real frames (the screencast only emits frames on changes).
await painted();
const tEnd = Date.now();
if (cdp) {
  for (let i = 0; i < 50 && !frames.some((f) => f.t >= tEnd); i += 1) {
    await page.evaluate(() => {
      let d = document.getElementById('demo-tick');
      if (!d) {
        d = document.createElement('div');
        d.id = 'demo-tick';
        d.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;z-index:2147483647;pointer-events:none';
        document.documentElement.appendChild(d);
      }
      d.style.background = d.style.background === 'rgb(255, 255, 254)' ? 'rgb(255, 255, 255)' : 'rgb(255, 255, 254)';
    }).catch(() => {});
    await page.waitForTimeout(100);
  }
}

if (cdp) await cdp.send('Page.stopScreencast').catch(() => {});
const video = page.video();
await context.close();
await browser.close();
server.close();

// --- encode ---
const mp4 = path.join(OUT, `${demo}.mp4`);
const trimStart = (tStart - tVideo0) / 1000;
const duration = (tEnd - tStart) / 1000;
if (capture === 'screencast') {
  let backwards = 0;
  for (let i = 1; i < frames.length; i += 1) if (frames[i].t < frames[i - 1].t) backwards += 1;
  const lag = frames.map((f) => f.arr - f.t).sort((a, b) => a - b);
  // Sort by capture time, drop duplicates (same frame delivered twice by overlapping screencasts).
  const sorted = frames.slice().sort((a, b) => a.t - b.t).filter((f, i, a) => i === 0 || f.t - a[i - 1].t > 0.5);
  console.log(`frames=${frames.length} unique=${sorted.length} out-of-order=${backwards} ` +
    `arrival-lag median=${lag[lag.length >> 1]?.toFixed(0)}ms max=${lag[lag.length - 1]?.toFixed(0)}ms`);
  // Screencast frame timestamps are wall-clock; build a concat list with per-frame durations.
  const list = [];
  const rel = sorted.map((f) => ({ ...f, s: (f.t - tStart) / 1000 }));
  // Keep the last frame before tStart as the opening frame.
  const firstIdx = Math.max(0, rel.findIndex((f) => f.s >= 0) - 1);
  const used = rel.slice(firstIdx).filter((f) => f.s <= duration);
  for (let i = 0; i < used.length; i += 1) {
    const s = Math.max(0, used[i].s);
    const next = i + 1 < used.length ? Math.max(0, used[i + 1].s) : duration;
    const d = Math.max(0.001, next - s);
    list.push(`file '${used[i].file}'`, `duration ${d.toFixed(4)}`);
  }
  list.push(`file '${used[used.length - 1].file}'`);
  fs.writeFileSync(path.join(RAW, 'frames.txt'), list.join('\n'));
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(RAW, 'frames.txt'),
    '-vf', `fps=${FPS},scale=${W}:${H}:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
    '-tune', 'stillimage', '-movflags', '+faststart', '-t', duration.toFixed(3), mp4]);
} else {
  const webm = await video.path();
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-ss', trimStart.toFixed(3), '-i', webm, '-t', duration.toFixed(3),
    '-vf', `fps=${FPS},format=yuv420p`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-movflags', '+faststart', mp4]);
}

// --- stills at marks + GIF preview ---
const stills = [];
for (const [name, t] of Object.entries(marks)) {
  const at = Math.max(0, Math.min(duration - 0.05, (t - tStart) / 1000));
  const png = path.join(OUT, `${demo}-${name}.png`);
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-ss', at.toFixed(3), '-i', mp4, '-frames:v', '1', png]);
  stills.push(png);
}
const gif = path.join(OUT, `${demo}-preview.gif`);
const palette = path.join(RAW, 'palette.png');
const gifFilter = 'fps=10,scale=960:-1:flags=lanczos';
execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', mp4, '-vf', `${gifFilter},palettegen=max_colors=128:stats_mode=diff`, palette]);
execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', mp4, '-i', palette, '-lavfi', `${gifFilter}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`, gif]);

fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify(Object.fromEntries(Object.entries(marks).map(([k, t]) => [k, (t - tStart) / 1000])), null, 2));
let cuesFile;
if (Object.keys(cueTimes).length) {
  cuesFile = path.join(OUT, 'cues.json');
  fs.writeFileSync(cuesFile, JSON.stringify(cueTimes, null, 2));
  const unsaid = (script.cues || []).map((c, i) => c.id ?? String(i)).filter((id) => !(id in cueTimes));
  if (unsaid.length) console.warn(`[narration] script cues never said (narrate.py falls back to their start/scene): ${unsaid.join(', ')}`);
}
if (!args.includes('--keep-raw')) fs.rmSync(RAW, { recursive: true, force: true });
console.log(JSON.stringify({ mp4, gif, stills, cues: cuesFile, duration, capture }, null, 2));

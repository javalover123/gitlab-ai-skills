// Quick screenshot of one route of a BUILT demo, printing console errors/warnings and unmocked calls:
//   node harness/shot.mjs <slug> <route> [out.png] [waitMs]
// e.g. node harness/shot.mjs shell-smoke /groups/acme-corp/-/edit out/shot.png 2500
import path from 'node:path';
import { startServer } from './serve.mjs';
import { chromium, newDemoContext, loadScenarioMeta } from './browser.mjs';

const [slug, route = '/', out = path.resolve(import.meta.dirname, '../out', `${slug}-shot.png`), wait = '2500'] = process.argv.slice(2);
if (!slug) {
  console.error('usage: node harness/shot.mjs <slug> <route> [out.png] [waitMs]');
  process.exit(1);
}
const meta = await loadScenarioMeta(slug);
const server = await startServer({ slug });
const browser = await chromium.launch({ args: ['--font-render-hinting=none', '--disable-lcd-text'] });
const context = await newDemoContext(browser, { demoTime: meta.demoTime || '2026-09-25T15:40:00-04:00', timezoneId: meta.timezoneId || 'America/New_York' });
const page = await context.newPage();
page.on('console', (m) => { if (['error', 'warning'].includes(m.type()) || /mock-(apollo|backend)/.test(m.text())) console.log(`[${m.type()}]`, m.text().slice(0, 300)); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message.slice(0, 300)));
await page.goto(server.baseUrl + route);
await page.waitForTimeout(Number(wait));
await page.screenshot({ path: out });
await browser.close();
server.close();
console.log('saved', out);

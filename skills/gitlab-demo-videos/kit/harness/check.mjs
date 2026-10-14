// Smoke-check every concrete route of a BUILT demo: screenshot each page to out/<slug>/check/<name>.png
// and report page errors, console errors and unmocked GraphQL/REST calls.
//   node harness/check.mjs <slug> [waitMs]
import fs from 'node:fs';
import path from 'node:path';
import { startServer } from './serve.mjs';
import { chromium, newDemoContext, loadScenarioMeta } from './browser.mjs';

const [slug, wait = '2500'] = process.argv.slice(2);
if (!slug) {
  console.error('usage: node harness/check.mjs <slug> [waitMs]');
  process.exit(1);
}
const routes = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, '../app/.build', slug, 'pages/routes.json'), 'utf8'));
const OUT = path.resolve(import.meta.dirname, '../out', slug, 'check');
fs.mkdirSync(OUT, { recursive: true });
const meta = await loadScenarioMeta(slug);
const server = await startServer({ slug });
const browser = await chromium.launch({ args: ['--font-render-hinting=none', '--disable-lcd-text'] });
const context = await newDemoContext(browser, { demoTime: meta.demoTime || '2026-09-25T15:40:00-04:00', timezoneId: meta.timezoneId || 'America/New_York' });
let problems = 0;
for (const [route, file] of Object.entries(routes)) {
  if (/[:*]/.test(route)) { console.log(`skip pattern route ${route} (${file})`); continue; }
  const page = await context.newPage();
  const issues = [];
  page.on('console', (m) => { if (m.type() === 'error' || /no (resolver|GraphQL handler)/.test(m.text())) issues.push(`[${m.type()}] ${m.text().slice(0, 240)}`); });
  page.on('pageerror', (e) => issues.push(`[pageerror] ${e.message.slice(0, 240)}`));
  await page.goto(server.baseUrl + route);
  await page.waitForTimeout(Number(wait));
  const png = path.join(OUT, file.replace('.html', '.png'));
  await page.screenshot({ path: png });
  const hidden = await page.evaluate(() => Boolean(document.getElementById('demo-boot-hide')));
  if (hidden) issues.push('[shell] page never revealed (entry threw before boot finished?)');
  problems += issues.length;
  console.log(`${issues.length ? 'WARN' : 'ok  '} ${route} -> ${path.relative(process.cwd(), png)}`);
  issues.forEach((i) => console.log('      ', i));
  await page.close();
}
await browser.close();
server.close();
console.log(problems ? `${problems} issue(s)` : 'all pages clean');

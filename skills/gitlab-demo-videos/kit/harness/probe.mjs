// DOM probe helper for writing scenarios: evaluates a JS expression on a route of a BUILT demo.
//   node harness/probe.mjs <slug> <route> "<js expression>" [waitMs]
// e.g. node harness/probe.mjs shell-smoke /acme-corp "[...document.querySelectorAll('button')].map(b=>b.innerText.trim()).filter(Boolean)"
import { startServer } from './serve.mjs';
import { chromium, newDemoContext, loadScenarioMeta } from './browser.mjs';

const [slug, route = '/', expr = 'document.title', wait = '2500'] = process.argv.slice(2);
const meta = await loadScenarioMeta(slug);
const server = await startServer({ slug });
const browser = await chromium.launch();
const context = await newDemoContext(browser, { demoTime: meta.demoTime || '2026-09-25T15:40:00-04:00', timezoneId: meta.timezoneId || 'America/New_York' });
const page = await context.newPage();
page.on('pageerror', (e) => console.log('[pageerror]', e.message.slice(0, 300)));
await page.goto(server.baseUrl + route);
await page.waitForTimeout(Number(wait));
const result = await page.evaluate((src) => (0, eval)(src), expr);
console.log(typeof result === 'string' ? result : JSON.stringify(result, null, 1));
await browser.close();
server.close();

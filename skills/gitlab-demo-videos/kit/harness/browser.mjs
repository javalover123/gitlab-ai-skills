// Shared Playwright launcher for harness scripts.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
// Cloud sessions often preinstall Playwright globally (browsers in $PLAYWRIGHT_BROWSERS_PATH); locally,
// scripts/setup.sh installs it into tools/playwright. Look in $PLAYWRIGHT_NODE_ROOT, the global npm root
// next to this Node binary, and tools/playwright, then fall back to normal module resolution.
function loadPlaywright() {
  const roots = [
    process.env.PLAYWRIGHT_NODE_ROOT,
    path.join(path.dirname(path.dirname(process.execPath)), 'lib/node_modules'),
    path.resolve(import.meta.dirname, '../tools/playwright/node_modules'),
  ];
  for (const r of roots.filter(Boolean)) {
    const p = path.join(r, 'playwright');
    if (fs.existsSync(p)) return require(p);
  }
  return require('playwright');
}
export const { chromium } = loadPlaywright();
export const W = 1920;
export const H = 1080;

// Context with the demo clock, cursor overlay and caption overlay installed.
export async function newDemoContext(browser, { demoTime, timezoneId = 'UTC', cursorStart = { x: 1400, y: 640 }, recordVideo } = {}) {
  const context = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: 1,
    locale: 'en-US',
    timezoneId,
    ...(recordVideo ? { recordVideo } : {}),
  });
  if (demoTime) {
    const offset = new Date(demoTime).getTime() - Date.now();
    await context.addInitScript({
      content: fs.readFileSync(path.join(import.meta.dirname, 'fake_date.js'), 'utf8').replaceAll('__DEMO_OFFSET_MS__', String(offset)),
    });
  }
  await context.addInitScript({ path: path.join(import.meta.dirname, 'cursor_overlay.js') });
  await context.addInitScript({ path: path.join(import.meta.dirname, 'caption_overlay.js') });
  await context.addInitScript({
    content: `try{if(!sessionStorage.getItem("__demoCursorPos"))sessionStorage.setItem('__demoCursorPos', ${JSON.stringify(JSON.stringify(cursorStart))})}catch(e){}`,
  });
  return context;
}

export async function loadScenarioMeta(slug) {
  const f = path.resolve(import.meta.dirname, '../app/demos', slug, 'scenario.mjs');
  if (!fs.existsSync(f)) return {};
  return (await import(f)).meta || {};
}

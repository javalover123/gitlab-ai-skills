// Build one demo: generate its pages and run Vite into app/.build/<slug>/dist.
//   node harness/build.mjs <slug>
// Safe to run for different slugs in parallel (separate pages/dist/cache dirs).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { genPages } from '../app/build/gen_pages.mjs';

const APP = path.resolve(import.meta.dirname, '../app');

export async function buildDemo(slug) {
  await genPages(slug);
  const t0 = Date.now();
  execFileSync(path.join(APP, 'node_modules/.bin/vite'), ['build'], {
    cwd: APP,
    env: { ...process.env, DEMO: slug },
    stdio: ['ignore', 'ignore', 'inherit'],
  });
  console.log(`vite build ${slug} done in ${((Date.now() - t0) / 1000).toFixed(0)}s -> app/.build/${slug}/dist`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(fs.realpathSync(process.argv[1])).href) {
  const slug = process.argv[2];
  if (!slug) {
    console.error('usage: node harness/build.mjs <slug>');
    process.exit(1);
  }
  await buildDemo(slug);
}

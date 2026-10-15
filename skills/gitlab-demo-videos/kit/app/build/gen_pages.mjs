// Generates the static HTML pages of ONE demo from app/demos/<slug>/pages.mjs into
// app/.build/<slug>/pages/*.html, plus routes.json (URL -> html file) for harness/serve.mjs.
// Each demo builds into its own .build/<slug>/ folder, so several demos can build/record in parallel.
//
//   node build/gen_pages.mjs <slug>
//
// pages.mjs default export: an array of page definitions (see src/shell/layout.mjs for fields), or a
// function returning one. `entry` is relative to the demo folder (default: the shell boot only).
// `route` may contain :params or end in * (e.g. a vue-router app); `routes: [...]` adds aliases.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { renderPage } from '../src/shell/layout.mjs';

const APP = path.resolve(import.meta.dirname, '..');

export function demoPaths(slug) {
  const build = path.join(APP, '.build', slug);
  return {
    demo: path.join(APP, 'demos', slug),
    build,
    pages: path.join(build, 'pages'),
    dist: path.join(build, 'dist'),
  };
}

const nameFromRoute = (route) =>
  route
    .replace(/^\/+|\/+$/g, '')
    .replace(/\/-\//g, '/')
    .replace(/[^A-Za-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'index';

export async function genPages(slug) {
  const p = demoPaths(slug);
  if (!fs.existsSync(path.join(p.demo, 'pages.mjs'))) throw new Error(`no such demo: app/demos/${slug}/pages.mjs`);
  const mod = await import(`${path.join(p.demo, 'pages.mjs')}?t=${Date.now()}`);
  const pages = typeof mod.default === 'function' ? await mod.default() : mod.default;

  fs.rmSync(p.pages, { recursive: true, force: true });
  fs.mkdirSync(p.pages, { recursive: true });
  const routes = {};
  const seen = new Set();
  for (const page of pages) {
    const name = page.name || nameFromRoute(page.route);
    if (seen.has(name)) throw new Error(`duplicate page name "${name}" in demo ${slug}`);
    seen.add(name);
    const entryAbs = page.entry ? path.resolve(p.demo, page.entry) : path.join(APP, 'src/shell/boot.js');
    if (!fs.existsSync(entryAbs)) throw new Error(`entry not found for page ${name}: ${entryAbs}`);
    const entry = path.relative(p.pages, entryAbs).split(path.sep).join('/');
    fs.writeFileSync(path.join(p.pages, `${name}.html`), renderPage({ ...page, entry }));
    for (const r of [page.route, ...(page.routes || [])]) routes[r] = `${name}.html`;
  }
  fs.writeFileSync(path.join(p.pages, 'routes.json'), JSON.stringify(routes, null, 2));
  console.log(`generated ${pages.length} page(s) for demo "${slug}" -> ${path.relative(APP, p.pages)}`);
  return { pages, routes };
}

if (process.argv[1] && import.meta.url === pathToFileURL(fs.realpathSync(process.argv[1])).href) {
  const slug = process.argv[2] || process.env.DEMO;
  if (!slug) {
    console.error('usage: node build/gen_pages.mjs <slug>');
    process.exit(1);
  }
  await genPages(slug);
}

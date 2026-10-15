// Compiles GitLab's real application stylesheet (v19.4.1-ee) plus Tailwind utilities,
// mirroring gl-src/scripts/frontend/lib/compile_css.mjs.
//
//   node build/build_css.mjs                 # application + fonts + tailwind + EVERY page bundle (CE + EE)
//   node build/build_css.mjs page_bundles/settings.scss   # just the named sources
//
// Output: public/assets/<path with / -> _>.css, e.g. page_bundles/settings.scss -> page_bundles_settings.css.
// EE page bundles (ee/app/assets/stylesheets/page_bundles/*) overwrite CE ones with the same name, as in GitLab.
// This is SHARED output: run it once from the shell owner, not from per-demo work.
import { writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { compile, Logger } from 'sass';
import postcss from 'postcss';
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';
import glob from 'glob';
import tailwindConfig from './tailwind.config.cjs';

const ROOT = path.resolve(import.meta.dirname, '../../gl-src');
const OUT = path.resolve(import.meta.dirname, '../public/assets');
mkdirSync(OUT, { recursive: true });

const loadPaths = [
  'ee/app/assets/stylesheets',
  'app/assets/stylesheets',
  'ee/app/assets/stylesheets/_ee',
  'app/assets/stylesheets/_ee',
  'app/assets/stylesheets/_jh',
  'node_modules/@gitlab/ui/src/vendor',
  'node_modules',
].map((p) => path.join(ROOT, p));

// [logical name, absolute source]
function allTargets() {
  const list = ['application.scss', 'fonts.scss', 'tailwind.css'].map((t) => [t, path.join(ROOT, 'app/assets/stylesheets', t)]);
  for (const base of ['app/assets/stylesheets', 'ee/app/assets/stylesheets']) {
    for (const f of glob.sync('page_bundles/**/*.scss', { cwd: path.join(ROOT, base), ignore: ['**/_*.scss'] })) {
      list.push([f, path.join(ROOT, base, f)]);
    }
  }
  return list;
}

const args = process.argv.slice(2);
const targets = args.length
  ? args.map((t) => {
      const ee = path.join(ROOT, 'ee/app/assets/stylesheets', t);
      return [t, existsSync(ee) ? ee : path.join(ROOT, 'app/assets/stylesheets', t)];
    })
  : allTargets();

let failed = 0;
for (const [t, src] of targets) {
  let css;
  if (t.endsWith('.css')) css = readFileSync(src, 'utf8');
  else {
    try {
      css = compile(src, { loadPaths, logger: Logger.silent, style: 'expanded' }).css;
    } catch (e) {
      failed += 1;
      console.error('FAILED', t, e.message.split('\n').slice(0, 4).join(' | '));
      continue;
    }
  }
  const res = await postcss([tailwindcss(tailwindConfig), autoprefixer()]).process(css, { from: src });
  const dest = path.join(OUT, t.replace(/\.scss$/, '.css').replace(/\//g, '_'));
  writeFileSync(dest, res.css);
  console.log('wrote', path.basename(dest), (res.css.length / 1024).toFixed(0) + 'KB');
}
if (failed) console.log(`${failed} stylesheet(s) failed (see above)`);

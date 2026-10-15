import path from 'node:path';
import fs from 'node:fs';
import { defineConfig } from 'vite';
import vue2 from '@vitejs/plugin-vue2';
import graphql from './build/vite_plugin_graphql.mjs';

const ROOT = path.resolve(import.meta.dirname, '../gl-src');
const JS = path.join(ROOT, 'app/assets/javascripts');
const EE_JS = path.join(ROOT, 'ee/app/assets/javascripts');
const STUBS = path.resolve(import.meta.dirname, 'src/stubs');

// One demo per build: DEMO=<slug> vite build  (harness/record.mjs and harness/build.mjs set it).
// Inputs are auto-discovered: every page generated into .build/<slug>/pages by build/gen_pages.mjs
// (which in turn reads app/demos/<slug>/pages.mjs). Nothing here needs editing for a new demo.
const DEMO = process.env.DEMO;
if (!DEMO) throw new Error('Set DEMO=<slug> (a folder in app/demos/). Use: node harness/build.mjs <slug>');
const BUILD = path.resolve(import.meta.dirname, '.build', DEMO);
const PAGES = path.join(BUILD, 'pages');
if (!fs.existsSync(PAGES)) throw new Error(`No generated pages for ${DEMO}; run node build/gen_pages.mjs ${DEMO} first`);

const inputs = Object.fromEntries(
  fs.readdirSync(PAGES).filter((f) => f.endsWith('.html')).map((f) => [f.replace('.html', ''), path.join(PAGES, f)]),
);

export default defineConfig({
  root: PAGES,
  base: '/',
  publicDir: path.resolve(import.meta.dirname, 'public'),
  cacheDir: path.join(BUILD, '.vite'),
  logLevel: 'error', // GitLab sources emit thousands of harmless Rollup annotation warnings
  build: {
    outDir: path.join(BUILD, 'dist'),
    emptyOutDir: true,
    rollupOptions: { input: inputs },
    chunkSizeWarningLimit: 100000,
    minify: 'esbuild',
    sourcemap: false,
  },
  resolve: {
    alias: [
      // Stubs for things that only make sense inside a real GitLab (Sentry, tracking, ...)
      { find: /^fe_islands\/.*$/, replacement: path.join(STUBS, 'fe_island.js') },
      { find: /^~\/sentry\/sentry_browser_wrapper$/, replacement: path.join(STUBS, 'sentry.js') },
      { find: /^@apollo\/client$/, replacement: '@apollo/client/core' },
      { find: /^@gitlab\/ui\/dist\/charts$/, replacement: '@gitlab/ui/src/charts' },
      { find: /^@gitlab\/ui$/, replacement: '@gitlab/ui/src' },
      { find: /^@gitlab\/svgs\/dist\/icons\.svg$/, replacement: path.join(JS, 'lib/utils/icons_path.js') },
      { find: /^@gitlab\/svgs\/dist\/illustrations\.svg$/, replacement: path.join(JS, 'lib/utils/illustrations_path.js') },
      { find: /^lodash$/, replacement: 'lodash-es' },
      { find: /^jquery$/, replacement: path.resolve(import.meta.dirname, 'node_modules/jquery/dist/jquery.slim.js') },
      { find: /^ee_component\/(.*)$/, replacement: `${EE_JS}/$1` },
      { find: /^ee_else_ce\/(.*)$/, replacement: `${EE_JS}/$1` },
      { find: /^jh_else_ce\/(.*)$/, replacement: `${JS}/$1` },
      { find: /^jh_else_ee\/(.*)$/, replacement: `${EE_JS}/$1` },
      { find: /^any_else_ce\/(.*)$/, replacement: `${EE_JS}/$1` },
      { find: /^ee\/(.*)$/, replacement: `${EE_JS}/$1` },
      { find: /^ee_images\/(.*)$/, replacement: `${ROOT}/ee/app/assets/images/$1` },
      { find: /^emojis\/(.*)$/, replacement: `${ROOT}/fixtures/emojis/$1` },
      { find: /^shared_queries\/(.*)$/, replacement: `${ROOT}/app/graphql/queries/$1` },
      { find: /^images\/(.*)$/, replacement: `${ROOT}/app/assets/images/$1` },
      { find: /^~\/(.*)$/, replacement: `${JS}/$1` },
      { find: /^@demo\/(.*)$/, replacement: `${path.resolve(import.meta.dirname)}/$1` },
    ],
    extensions: ['.mjs', '.js', '.json', '.vue', '.graphql'],
  },
  plugins: [
    graphql(),
    vue2({ template: { compilerOptions: { whitespace: 'preserve' } } }),
  ],
  define: {
    IS_EE: JSON.stringify('typeof window !== "undefined" && window.gon && window.gon.ee'),
    IS_JH: JSON.stringify(false),
    'process.platform': JSON.stringify(''),
    'process.env.NODE_ENV': JSON.stringify('production'),
    'window.IS_VITE': JSON.stringify(true),
  },
});

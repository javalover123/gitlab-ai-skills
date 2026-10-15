// Static server for ONE built demo (app/.build/<slug>/dist). Maps GitLab-style URLs to the demo's
// generated pages (routes.json; exact routes first, then :param / trailing-* patterns) and answers
// REST calls from app/demos/<slug>/rest.mjs. Unknown /api/ and /-/ paths get an empty JSON body.
//
//   node harness/serve.mjs <slug> [port]      # manual browsing, default port 0 = any free port
//
// rest.mjs default export: { '<METHOD> <path>' | '<path>': value | (req) => value }
//   value: JSON body, or { status, data, headers } envelope, or { redirect: '/path', flash: { notice: '...' } }
//   (redirect answers 303 + a demo_flash cookie that shell/boot.js renders like layouts/_flash - use it for
//   HAML forms, e.g. 'POST /groups/acme-corp': () => ({ redirect: '/groups/acme-corp/-/edit', flash: { notice: "Group 'Acme Corp' was successfully updated." } }))
//   req: { method, path, query, params, body }   (body: parsed JSON or form fields; Rails `_method` is honoured)
// Browser-side calls are usually better mocked in the entry with mockBackend (src/shell/mock_backend.js);
// rest.mjs is for full-page navigations/form posts and fetches you cannot intercept in the page.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const APP = path.resolve(import.meta.dirname, '../app');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.json': 'application/json',
  '.gif': 'image/gif', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon',
};

function compile(key) {
  const m = key.match(/^([A-Z]+)\s+(.*)$/);
  const method = m ? m[1] : null;
  const p = m ? m[2] : key;
  const names = [];
  const re = new RegExp(`^${p.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*$/, '.*').replace(/:([A-Za-z_]+)/g, (_, n) => { names.push(n); return '([^/]+)'; })}$`);
  return { method, re, names, exact: !/[:*]/.test(p) };
}

const decode = (s) => {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
};

const readBody = (req) =>
  new Promise((resolve) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      if (!raw) return resolve(undefined);
      try {
        return resolve(JSON.parse(raw));
      } catch (e) {
        return resolve(Object.fromEntries(new URLSearchParams(raw)));
      }
    });
  });

export async function startServer(slugOrOpts = {}, portArg = 0) {
  const opts = typeof slugOrOpts === 'string' ? { slug: slugOrOpts, port: portArg } : slugOrOpts;
  const { slug, port = 0 } = opts;
  if (!slug) throw new Error('startServer: demo slug required');
  const BUILD = path.join(APP, '.build', slug);
  const DIST = path.join(BUILD, 'dist');
  if (!fs.existsSync(DIST)) throw new Error(`demo "${slug}" is not built; run: node harness/build.mjs ${slug}`);
  const routeMap = JSON.parse(fs.readFileSync(path.join(BUILD, 'pages/routes.json'), 'utf8'));
  const routes = Object.entries(routeMap).map(([r, file]) => ({ ...compile(r), file }));
  routes.sort((a, b) => Number(b.exact) - Number(a.exact));
  const restFile = path.join(APP, 'demos', slug, 'rest.mjs');
  const restMap = fs.existsSync(restFile) ? (await import(`${restFile}?t=${Date.now()}`)).default : {};
  const rest = Object.entries(restMap).map(([k, handler]) => ({ ...compile(k), handler }));

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    let method = req.method;
    let body;
    if (!['GET', 'HEAD'].includes(method)) {
      body = await readBody(req);
      if (body && typeof body === 'object' && body._method) method = String(body._method).toUpperCase();
    }
    for (const r of rest) {
      if (r.method && r.method !== method) continue;
      const m = url.pathname.match(r.re);
      if (!m) continue;
      const params = Object.fromEntries(r.names.map((n, i) => [n, decode(m[i + 1])]));
      let out = typeof r.handler === 'function' ? await r.handler({ method, path: url.pathname, query: Object.fromEntries(url.searchParams), params, body }) : r.handler;
      if (out && typeof out === 'object' && !Array.isArray(out) && typeof out.redirect === 'string') {
        const headers = { location: out.redirect };
        if (out.flash) headers['set-cookie'] = `demo_flash=${encodeURIComponent(JSON.stringify(out.flash))}; Path=/`;
        res.writeHead(303, headers);
        res.end();
        return;
      }
      const env = out && typeof out === 'object' && !Array.isArray(out) && typeof out.status === 'number' && 'data' in out ? out : { status: 200, data: out };
      res.writeHead(env.status, { 'content-type': 'application/json', ...(env.headers || {}) });
      res.end(JSON.stringify(env.data ?? null));
      return;
    }
    const route = routes.find((r) => r.re.test(url.pathname));
    let file = route ? path.join(DIST, route.file) : path.join(DIST, decode(url.pathname));
    if (file !== DIST && !file.startsWith(DIST + path.sep)) file = DIST;
    if (fs.existsSync(file) && fs.statSync(file).isFile()) {
      res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
      fs.createReadStream(file).pipe(res);
      return;
    }
    // Anything else (REST/GraphQL calls the real shell makes) -> empty JSON.
    res.writeHead(url.pathname.startsWith('/api/') || url.pathname.includes('/-/') ? 200 : 404, { 'content-type': 'application/json' });
    res.end(url.pathname === '/api/graphql' ? '{"data":{}}' : '[]');
  });
  await new Promise((resolve) => server.listen(port, '127.0.0.1', resolve));
  server.baseUrl = `http://127.0.0.1:${server.address().port}`;
  return server;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [slug, port = process.env.PORT || 0] = process.argv.slice(2);
  const s = await startServer({ slug, port: Number(port) });
  console.log(`serving ${slug} on ${s.baseUrl}`);
}

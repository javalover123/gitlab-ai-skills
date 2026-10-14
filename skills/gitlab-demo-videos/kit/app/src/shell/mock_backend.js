// In-browser mock backend for code that talks to GitLab over HTTP with its OWN clients:
//   - GraphQL through ~/lib/graphql createDefaultClient (fetch POST /api/graphql, batched or not)
//   - REST through ~/lib/utils/axios_utils (axios) or window.fetch
// so a page can call GitLab's real init functions (e.g. `initAiSettings()`) unmodified and still run offline.
// shell/boot.js installs it before anything mounts; entries register handlers:
//
//   import { mockBackend } from '@demo/src/shell/boot';
//   mockBackend.graphql({ getAiFlowTriggers: (vars) => ({ project: {...} }) });
//   mockBackend.rest({
//     'GET /api/v4/groups/:id': ({ params }) => ({ id: Number(params.id), name: 'Acme Corp' }),
//     'PUT /api/v4/groups/:id': ({ body }) => ({ ...body }),           // body is parsed JSON / form object
//     '/api/v4/projects/2001/flow_triggers': [ ... ],                  // any method, static JSON
//     'POST /-/foo': () => ({ status: 422, data: { message: 'nope' } }),
//   });
//   mockBackend.latency = 350;   // ms, default for every mocked response
//
// Handler return value: plain JSON (status 200), or { status, data, headers } (detected by a numeric `status`
// plus a `data` key). Paths may use :params and a trailing *. Query strings are ignored for matching
// (available as `query`). Anything unmatched goes to the real network (harness/serve.mjs, which answers
// unknown /api and /-/ paths with an empty JSON body).
import axios from '~/lib/utils/axios_utils';

const gqlHandlers = {};
const restHandlers = [];
const log = (...a) => console.info('[mock-backend]', ...a); // eslint-disable-line no-console

function compile(key) {
  const m = key.match(/^([A-Z]+)\s+(.*)$/);
  const method = m ? m[1] : null;
  const path = m ? m[2] : key;
  const names = [];
  const re = new RegExp(
    `^${path
      .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
      .replace(/\\\*$|\*$/, '(?<__rest>.*)')
      .replace(/:([A-Za-z_]+)/g, (_, n) => {
        names.push(n);
        return '([^/]+)';
      })}$`,
  );
  return { method, re, names };
}

function matchRest(method, url) {
  const u = new URL(url, window.location.origin);
  if (u.origin !== window.location.origin) return null;
  for (let i = restHandlers.length - 1; i >= 0; i -= 1) {
    const h = restHandlers[i];
    if (h.method && h.method !== method) continue;
    const m = u.pathname.match(h.re);
    if (m) {
      const params = Object.fromEntries(h.names.map((n, idx) => [n, decodeURIComponent(m[idx + 1])]));
      return { handler: h.handler, params, query: Object.fromEntries(u.searchParams), path: u.pathname };
    }
  }
  return null;
}

const isEnvelope = (r) => r && typeof r === 'object' && !Array.isArray(r) && typeof r.status === 'number' && 'data' in r;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function runRest(hit, method, body) {
  const out = typeof hit.handler === 'function' ? await hit.handler({ method, body, params: hit.params, query: hit.query, path: hit.path }) : hit.handler;
  return isEnvelope(out) ? { headers: {}, ...out } : { status: 200, data: out, headers: {} };
}

function parseBody(body) {
  if (body == null) return undefined;
  if (typeof body === 'string') {
    try {
      return JSON.parse(body);
    } catch (e) {
      return Object.fromEntries(new URLSearchParams(body));
    }
  }
  if (typeof FormData !== 'undefined' && body instanceof FormData) return Object.fromEntries(body.entries());
  return body;
}

async function runGraphql(payload) {
  const ops = Array.isArray(payload) ? payload : [payload];
  const results = await Promise.all(
    ops.map(async (op) => {
      const h = gqlHandlers[op.operationName];
      if (!h) {
        console.warn('[mock-backend] no GraphQL handler for', op.operationName); // eslint-disable-line no-console
        return { data: null };
      }
      try {
        return { data: await h(op.variables || {}, op) };
      } catch (e) {
        return { data: null, errors: [{ message: e.message }] };
      }
    }),
  );
  return Array.isArray(payload) ? results : results[0];
}

export const mockBackend = {
  latency: 300,
  graphql(map) {
    Object.assign(gqlHandlers, map);
    return this;
  },
  rest(map) {
    Object.entries(map).forEach(([key, handler]) => restHandlers.push({ ...compile(key), handler }));
    return this;
  },
  hasGraphql: (name) => Boolean(gqlHandlers[name]),
};

let installed = false;
export function installMockBackend() {
  if (installed) return mockBackend;
  installed = true;

  // --- fetch (Apollo HTTP / BatchHttp links, some REST) ---
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    const method = (init.method || (typeof input !== 'string' && input.method) || 'GET').toUpperCase();
    const path = new URL(url, window.location.origin).pathname;
    if (path === '/api/graphql' && method === 'POST') {
      const payload = JSON.parse(init.body);
      const names = (Array.isArray(payload) ? payload : [payload]).map((p) => p.operationName);
      if (names.some((n) => gqlHandlers[n])) {
        await wait(mockBackend.latency);
        return new Response(JSON.stringify(await runGraphql(payload)), { status: 200, headers: { 'content-type': 'application/json' } });
      }
      log('graphql passthrough', names.join(','));
    }
    const hit = matchRest(method, url);
    if (hit) {
      await wait(mockBackend.latency);
      const res = await runRest(hit, method, parseBody(init.body));
      return new Response(JSON.stringify(res.data ?? null), { status: res.status, headers: { 'content-type': 'application/json', ...res.headers } });
    }
    return realFetch(input, init);
  };

  // --- axios (~/lib/utils/axios_utils) ---
  const realAdapter = axios.defaults.adapter;
  axios.defaults.adapter = async (config) => {
    const method = (config.method || 'get').toUpperCase();
    const url = config.baseURL && !/^https?:/.test(config.url) ? `${config.baseURL}${config.url}` : config.url;
    const hit = matchRest(method, url);
    if (!hit) return realAdapter(config);
    await wait(mockBackend.latency);
    const res = await runRest(hit, method, parseBody(config.data));
    const response = { data: res.data, status: res.status, statusText: String(res.status), headers: res.headers, config, request: {} };
    if (res.status >= 400) {
      const err = new Error(`Request failed with status code ${res.status}`);
      err.response = response;
      err.config = config;
      throw err;
    }
    return response;
  };
  return mockBackend;
}

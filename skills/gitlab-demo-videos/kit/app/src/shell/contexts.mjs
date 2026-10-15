// Fictional org shared by every demo. Import from pages.mjs / entry files:
//   import { USER, GROUPS, PROJECTS, group, project } from '@demo/src/shell/contexts.mjs';  (browser, via Vite alias)
//   import { USER, GROUPS, PROJECTS } from '../../src/shell/contexts.mjs';                   (Node, pages.mjs)
// A demo that needs another group/project passes its own object with the same shape as page.group / page.project
// instead of editing this file.

export const USER = {
  id: 4242,
  gid: 'gid://gitlab/User/4242',
  name: 'Alex Rivera',
  username: 'arivera',
  avatarUrl: '/uploads/avatar.svg',
  webUrl: '/arivera',
  email: 'alex.rivera@acme.example',
};

// Group shape: { id, name, path, fullPath, fullName, parent (fullPath|null), avatarUrl, plan, description }
export const GROUPS = {
  'acme-corp': {
    id: 101,
    name: 'Acme Corp',
    path: 'acme-corp',
    fullPath: 'acme-corp',
    fullName: 'Acme Corp',
    parent: null,
    avatarUrl: null, // null -> GitLab identicon (letter avatar), like a group without an uploaded avatar
    plan: 'ultimate',
    description: 'Acme Corp engineering',
  },
  'acme-corp/payments': {
    id: 131,
    name: 'Payments',
    path: 'payments',
    fullPath: 'acme-corp/payments',
    fullName: 'Acme Corp / Payments',
    parent: 'acme-corp',
    avatarUrl: null,
    plan: 'ultimate',
    description: 'Payments platform team',
  },
  'acme-labs': {
    id: 102,
    name: 'Acme Labs',
    path: 'acme-labs',
    fullPath: 'acme-labs',
    fullName: 'Acme Labs',
    parent: null,
    avatarUrl: null,
    plan: 'premium',
    description: 'Acme Labs R&D',
  },
};

// Project shape: { id, name, path, fullPath, fullName, namespace (group fullPath), defaultBranch, avatarUrl }
export const PROJECTS = {
  'acme-corp/checkout-service': {
    id: 2001,
    name: 'checkout-service',
    path: 'checkout-service',
    fullPath: 'acme-corp/checkout-service',
    fullName: 'Acme Corp / checkout-service',
    namespace: 'acme-corp',
    defaultBranch: 'main',
    avatarUrl: null,
    description: 'Checkout and payment orchestration API',
  },
  'acme-corp/payments/ledger-api': {
    id: 2017,
    name: 'ledger-api',
    path: 'ledger-api',
    fullPath: 'acme-corp/payments/ledger-api',
    fullName: 'Acme Corp / Payments / ledger-api',
    namespace: 'acme-corp/payments',
    defaultBranch: 'main',
    avatarUrl: null,
    description: 'Double-entry ledger service',
  },
};

export const resolveGroup = (g) => (typeof g === 'string' ? GROUPS[g] : g) || null;
export const resolveProject = (p) => (typeof p === 'string' ? PROJECTS[p] : p) || null;

// Group ancestry root-first (for breadcrumbs), using GROUPS for lookups.
export function groupChain(g, extraGroups = {}) {
  const all = { ...GROUPS, ...extraGroups };
  const chain = [];
  let cur = resolveGroup(g);
  while (cur) {
    chain.unshift(cur);
    cur = cur.parent ? all[cur.parent] : null;
  }
  return chain;
}

// Handy URL helpers (same shapes as the Rails route helpers).
export const groupPath = (g) => `/${resolveGroup(g).fullPath}`;
export const groupDashPath = (g, rest = '') => `/groups/${resolveGroup(g).fullPath}/-/${rest}`;
export const projectPath = (p) => `/${resolveProject(p).fullPath}`;
export const projectDashPath = (p, rest = '') => `/${resolveProject(p).fullPath}/-/${rest}`;
export const gid = (type, id) => `gid://gitlab/${type}/${id}`;

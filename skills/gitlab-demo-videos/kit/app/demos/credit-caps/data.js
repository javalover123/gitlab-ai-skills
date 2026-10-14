// Synthetic GitLab Credits data for the "Set credit caps and unblock a user" demo (Acme Corp, Sep 2026).
// Nothing here comes from production. Shapes follow
//   ee/app/assets/javascripts/usage_quotas/wallet_agnostic_credits_dashboard/index/graphql/*.graphql
//   ee/app/assets/javascripts/usage_quotas/wallet_agnostic_credits_dashboard/credit_caps/graphql/*.graphql
// and the spec mock data next to them.

export const NAMESPACE = 'acme-corp';
export const DEMO_TODAY = '2026-09-25';

// GitLab-style letter identicon (users without an uploaded avatar).
const IDENTICON_BG = ['#fcf1ef', '#f4f0ff', '#f1f1ff', '#e9f3fc', '#ecf4ee', '#fdf1dd', '#ececef'];
const IDENTICON_FG = ['#8f2110', '#5c47a6', '#3f3fa6', '#0b5cad', '#24663b', '#8f4700', '#3a383f'];
function identicon(name, id) {
  const i = id % IDENTICON_BG.length;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="${IDENTICON_BG[i]}"/><text x="32" y="42" text-anchor="middle" font-family="GitLab Sans,Arial,sans-serif" font-size="28" font-weight="600" fill="${IDENTICON_FG[i]}">${name[0].toUpperCase()}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

// Month-to-date credits per user (sorted high -> low as the dashboard shows them by default).
const RAW_USERS = [
  [5101, 'Priya Natarajan', 'pnatarajan', 438],
  [5102, 'Marcus Chen', 'mchen', 362],
  [5190, 'Code Review Flow', 'duo-code-review-acme-corp', 341, 'non_human'],
  [5103, 'Sofia Alvarez', 'salvarez', 318],
  [4242, 'Alex Rivera', 'arivera', 244],
  [5104, 'Jordan Blake', 'jblake', 212],
  [5105, 'Hana Kobayashi', 'hkobayashi', 187],
  [5106, 'Omar Haddad', 'ohaddad', 165],
  [5107, 'Lena Fischer', 'lfischer', 142],
  [5108, 'Tomás Ribeiro', 'tribeiro', 118],
  [5109, 'Grace Okafor', 'gokafor', 104],
  [5110, 'Daniel Park', 'dpark', 96],
  [5111, 'Ines Moreau', 'imoreau', 88],
  [5112, 'Ravi Shah', 'rshah', 81],
  [5113, 'Chloe Martin', 'cmartin', 73],
  [5114, 'Ethan Walsh', 'ewalsh', 66],
  [5115, 'Mei Lin', 'mlin', 58],
  [5116, 'Noah Schmidt', 'nschmidt', 51],
  [5117, 'Aisha Bello', 'abello', 44],
  [5118, 'Lucas Rossi', 'lrossi', 37],
];

export const USERS = RAW_USERS.map(([id, name, username, credits, entityType = 'user']) => ({
  id,
  gid: `gid://gitlab/User/${id}`,
  name,
  username,
  credits,
  entityType,
  avatarUrl: id === 4242 ? '/uploads/avatar.svg' : identicon(name, id),
  webPath: `/${username}`,
}));

export const TOTAL_ACTIVE_USERS = 46;
export const TOTAL_CREDITS = 9842;

// Daily totals for Sep 1..25 (weekends quiet), scaled to TOTAL_CREDITS.
function mulberry32(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(19401);
const raw = [];
for (let d = 1; d <= 25; d += 1) {
  const date = `2026-09-${String(d).padStart(2, '0')}`;
  const dow = new Date(`${date}T00:00:00Z`).getUTCDay();
  const weekend = dow === 0 || dow === 6;
  const burst = d === 16 ? 1.55 : d === 22 ? 1.3 : 1;
  raw.push({ date, w: (weekend ? 0.1 + rand() * 0.08 : 0.75 + rand() * 0.45) * burst });
}
const wSum = raw.reduce((s, r) => s + r.w, 0);
export const DAILY_USAGE = raw.map((r) => ({ date: r.date, creditsUsed: Math.round((r.w / wSum) * TOTAL_CREDITS) }));

export const PRODUCTS = [
  {
    id: 'duo_agent_platform',
    title: 'GitLab Duo Agent Platform',
    creditsUsed: TOTAL_CREDITS,
    flowTypes: [
      { id: 'chat', title: 'Agentic Chat' },
      { id: 'code_suggestions', title: 'Code Suggestions' },
      { id: 'code_review', title: 'Code Review Flow' },
      { id: 'software_development', title: 'Software Development Flow' },
      { id: 'fix_pipeline', title: 'Fix Pipeline Flow' },
    ],
  },
];

// Cap state shared by both pages (sessionStorage through demoState). Starts like a group that never set caps.
export const INITIAL_CAPS = { flatUserCap: null, flatUserCapEnabled: null, overrides: {} };

// A user is blocked when their usage reached the cap that applies to them (override first, then flat cap).
export function isBlocked(user, caps) {
  const o = caps.overrides[user.gid];
  if (o) return o.enabled && user.credits >= o.cap;
  return Boolean(caps.flatUserCapEnabled) && caps.flatUserCap != null && user.credits >= caps.flatUserCap;
}

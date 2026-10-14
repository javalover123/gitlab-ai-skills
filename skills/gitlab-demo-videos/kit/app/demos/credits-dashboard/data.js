// Synthetic GitLab Credits usage for the demo user. Nothing here comes from production.
// Shapes follow ee/app/assets/javascripts/usage_quotas/user_credits_dashboard/index/graphql/*.graphql
// (and ee/spec/frontend/usage_quotas/user_credits_dashboard/mock_data.js).

export const DEMO_TODAY = '2026-09-25'; // Friday

export const GROUPS = [
  { name: 'Acme Corp', path: 'acme-corp' },
  { name: 'Acme Labs', path: 'acme-labs' },
];

// Flow types, titles as they appear in GitLab's own usage-billing mock data.
export const PRODUCTS = [
  {
    id: 'duo_agent_platform',
    title: 'GitLab Duo Agent Platform',
    flowTypes: [
      { id: 'chat', title: 'Agentic Chat' },
      { id: 'code_suggestions', title: 'Code Suggestions' },
      { id: 'code_review', title: 'Code Review Flow' },
      { id: 'software_development', title: 'Software Development Flow' },
      { id: 'fix_pipeline', title: 'Fix Pipeline Flow' },
      { id: 'issue_to_merge_request', title: 'Issue to Merge Request Flow' },
    ],
  },
];

// Average weekday credits per flow type, per group.
const PROFILE = {
  'acme-corp': {
    chat: 5.25,
    code_suggestions: 3.1,
    code_review: 2.4,
    software_development: 4.6,
    fix_pipeline: 1.3,
    issue_to_merge_request: 1.9,
  },
  'acme-labs': {
    chat: 1.6,
    code_suggestions: 0.9,
    code_review: 0.4,
    software_development: 1.1,
    fix_pipeline: 0.2,
    issue_to_merge_request: 0.3,
  },
};

// Deterministic PRNG so every recording shows the same numbers.
function mulberry32(seed) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const hash = (s) => [...s].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) | 0, 7);

const iso = (d) => d.toISOString().slice(0, 10);
const addDays = (isoDate, n) => {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return iso(d);
};

const round1 = (n) => Math.round(n * 10) / 10;

// usage[group][date][flowType] = credits
const USAGE = {};
for (const { path } of GROUPS) {
  USAGE[path] = {};
  const rand = mulberry32(hash(path));
  for (let date = '2026-06-01'; date <= DEMO_TODAY; date = addDays(date, 1)) {
    const dow = new Date(`${date}T00:00:00Z`).getUTCDay();
    const weekend = dow === 0 || dow === 6;
    // A couple of heavier "crunch" days make the peak card interesting.
    const burst = date === '2026-09-16' ? 1.9 : date === '2026-09-22' ? 1.45 : 1;
    const day = {};
    for (const [flow, avg] of Object.entries(PROFILE[path])) {
      const active = weekend ? rand() < 0.22 : rand() < 0.93;
      const factor = weekend ? 0.18 : 0.55 + rand() * 0.9;
      day[flow] = active ? round1(avg * factor * burst) : 0;
    }
    USAGE[path][date] = day;
  }
}

export function creditsUsage({ namespacePath, startDate, endDate, flowTypes = [] }) {
  const byDate = USAGE[namespacePath] || {};
  const dailyUsage = [];
  let total = 0;
  for (let date = startDate; date <= endDate && date <= DEMO_TODAY; date = addDays(date, 1)) {
    const day = byDate[date];
    if (!day) continue;
    const credits = round1(
      Object.entries(day)
        .filter(([flow]) => !flowTypes.length || flowTypes.includes(flow))
        .reduce((sum, [, v]) => sum + v, 0),
    );
    total += credits;
    dailyUsage.push({ date, creditsUsed: credits });
  }
  return { creditsUsed: round1(total), dailyUsage };
}

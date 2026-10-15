// Pages for "Set credit caps and unblock a user" (GitLab 19.4, GitLab.com, top-level group Owner).
// Views: ee/app/views/groups/settings/gitlab_credits_dashboard/index.html.haml
//        ee/app/views/groups/settings/gitlab_credits_dashboard/credit_caps/index.html.haml
const G = 'acme-corp';
const DASH = `/groups/${G}/-/settings/gitlab_credits_dashboard`;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');

const gon = {
  features: { walletAgnosticCreditsDashboard: true, creditCapsUi: true },
  display_gitlab_credits_user_data: true,
};

// usage_billing_dashboard_data (ee/app/helpers/ee/groups/settings_helper.rb)
const dashData = {
  'user-usage-path': `${DASH}/users/__USERNAME__`,
  'namespace-path': G,
  'subscription-start-date': '2026-01-01',
  'upgrade-button-path': '#',
  'is-saas': 'true',
  'is-free': 'false',
  'is-paid-base-plan': 'true',
  'purchase-credits-path': '#',
  'credits-generalization-ui': 'false',
};
const dataAttrs = (o) => Object.entries(o).map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ');

export default [
  {
    name: 'dashboard',
    route: DASH,
    group: G,
    activeMenuId: 'gitlab_credits_dashboard',
    title: ['GitLab Credits dashboard'],
    crumbs: [{ text: 'GitLab Credits dashboard', href: DASH }],
    bodyPage: 'groups:settings:gitlab_credits_dashboard:index',
    entry: 'entry_dashboard.js',
    content: `<div id="js-group-usage-billing-dashboard" ${dataAttrs(dashData)}></div>`,
    gon,
  },
  {
    name: 'credit-caps',
    route: `${DASH}/credit_caps`,
    group: G,
    activeMenuId: 'gitlab_credits_dashboard',
    title: ['Credit caps'],
    crumbs: [
      { text: 'GitLab Credits dashboard', href: DASH },
      { text: 'Credit caps', href: `${DASH}/credit_caps` },
    ],
    bodyPage: 'groups:settings:gitlab_credits_dashboard:credit_caps:index',
    entry: 'entry_caps.js',
    content: `<div id="js-group-credit-caps-dashboard" data-namespace-path="${G}"></div>`,
    gon,
  },
];

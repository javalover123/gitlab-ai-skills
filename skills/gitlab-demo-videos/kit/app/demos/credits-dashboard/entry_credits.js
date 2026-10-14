// Mirrors ee/app/assets/javascripts/usage_quotas/user_credits_dashboard/index/index.js,
// but swaps GitLab's HTTP Apollo client for the in-browser mock (like app.stories.js does).
import '@demo/src/shell/boot';
import Vue from 'vue';
import VueApollo from 'vue-apollo';
import UserCreditsDashboardApp from 'ee/usage_quotas/user_credits_dashboard/index/components/app.vue';
import { createMockApolloClient } from '@demo/src/shell/mock_apollo';
import { PRODUCTS, creditsUsage } from './data';

const USER_ID = 'gid://gitlab/User/4242';

const client = createMockApolloClient({
  getUserBillingPeriodUsage: ({ namespacePath }) => {
    const startDate = '2026-09-01';
    const endDate = '2026-09-30';
    const { creditsUsed } = creditsUsage({ namespacePath, startDate, endDate });
    return {
      currentUser: {
        __typename: 'CurrentUser',
        id: USER_ID,
        creditsUsage: {
          __typename: 'GitlabSubscriptionUserCreditsUsage',
          enabled: true,
          isOutdatedClient: false,
          startDate,
          endDate,
          creditsUsed,
        },
      },
    };
  },
  getUserCreditsUsage: (vars) => {
    const { creditsUsed, dailyUsage } = creditsUsage(vars);
    return {
      currentUser: {
        __typename: 'CurrentUser',
        id: USER_ID,
        creditsUsage: {
          __typename: 'GitlabSubscriptionUserCreditsUsage',
          startDate: vars.startDate,
          endDate: vars.endDate,
          creditsUsed,
          dailyUsage: dailyUsage.map((d) => ({
            __typename: 'GitlabSubscriptionUserCreditsUsageDailyUsage',
            ...d,
          })),
          products: PRODUCTS.map((p) => ({
            __typename: 'GitlabSubscriptionUserCreditsUsageProduct',
            ...p,
            flowTypes: p.flowTypes.map((f) => ({ __typename: 'GitlabSubscriptionUsageFlowTypeInfo', ...f })),
          })),
          blockedStatus: {
            __typename: 'GitlabSubscriptionUsageBlockedStatus',
            blocked: false,
            capType: null,
          },
        },
      },
    };
  },
});

const el = document.getElementById('js-user-gitlab-credits-dashboard');
const { groupsWithGitlabCredits } = el.dataset;

Vue.use(VueApollo);

// eslint-disable-next-line no-new
new Vue({
  el,
  apolloProvider: new VueApollo({ defaultClient: client }),
  name: 'UserCreditsDashboardRoot',
  provide: { groups: JSON.parse(groupsWithGitlabCredits) },
  render(h) {
    return h(UserCreditsDashboardApp);
  },
});

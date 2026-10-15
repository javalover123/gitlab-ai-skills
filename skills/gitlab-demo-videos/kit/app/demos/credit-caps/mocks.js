// In-browser GitLab API for both pages of the demo. Cap settings live in demoState (sessionStorage),
// so a save on the Credit caps page changes Usage control status on the dashboard after navigating.
import { mockBackend, demoState } from '@demo/src/shell/boot';
import {
  USERS,
  TOTAL_ACTIVE_USERS,
  TOTAL_CREDITS,
  DAILY_USAGE,
  PRODUCTS,
  INITIAL_CAPS,
  isBlocked,
} from './data';

const KEY = 'credit-caps';
const caps = () => demoState.get(KEY, INITIAL_CAPS);
const saveCaps = (c) => demoState.set(KEY, c);

const PAGE_INFO = (hasNextPage) => ({
  __typename: 'PageInfo',
  hasNextPage,
  hasPreviousPage: false,
  startCursor: 'eyJpZCI6MX0',
  endCursor: 'eyJpZCI6MjB9',
});

const toGqlUser = (u) => ({
  __typename: 'User',
  id: u.gid,
  name: u.name,
  username: u.username,
  avatarUrl: u.avatarUrl,
  webPath: u.webPath,
  webUrl: u.webPath,
  status: null,
});

mockBackend.latency = 160;

mockBackend.graphql({
  getSubscriptionCreditsUsageOverview: ({ usersListSort }) => {
    const c = caps();
    const users = [...USERS];
    if (usersListSort === 'TOTAL_CREDITS_USED_ASC') users.reverse();
    if (usersListSort?.startsWith('NAME')) users.sort((a, b) => a.name.localeCompare(b.name));
    if (usersListSort === 'NAME_DESC') users.reverse();
    return {
      subscriptionUsage: {
        __typename: 'GitlabSubscriptionUsage',
        enabled: true,
        isOutdatedClient: false,
        startDate: '2026-09-01',
        endDate: '2026-09-30',
        creditsUsed: TOTAL_CREDITS,
        dailyAverage: Math.round(TOTAL_CREDITS / DAILY_USAGE.length),
        dailyUsage: DAILY_USAGE.map((d) => ({ __typename: 'GitlabSubscriptionUsageDailyUsage', ...d })),
        usersUsage: {
          __typename: 'GitlabSubscriptionUsageUsersUsage',
          totalActiveUsers: TOTAL_ACTIVE_USERS,
          users: {
            __typename: 'GitlabSubscriptionUsageUserConnection',
            nodes: users.map((u) => ({
              __typename: 'GitlabSubscriptionUsageUser',
              id: u.gid,
              name: u.name,
              username: u.username,
              avatarUrl: u.avatarUrl,
              entityType: u.entityType,
              usage: { __typename: 'GitlabSubscriptionUsageUserUsage', totalCreditsUsed: u.credits },
              blockedStatus: { __typename: 'GitlabSubscriptionUsageBlockedStatus', blocked: isBlocked(u, c) },
            })),
            pageInfo: PAGE_INFO(true),
          },
        },
        products: PRODUCTS.map((p) => ({
          __typename: 'GitlabSubscriptionUsageProduct',
          ...p,
          flowTypes: p.flowTypes.map((f) => ({ __typename: 'GitlabSubscriptionUsageFlowTypeInfo', ...f })),
        })),
      },
    };
  },

  getCreditCaps: () => {
    const c = caps();
    return {
      subscriptionUsage: {
        __typename: 'GitlabSubscriptionUsage',
        budgetCaps: {
          __typename: 'GitlabSubscriptionBudgetCaps',
          flatUserCap: c.flatUserCap,
          flatUserCapEnabled: c.flatUserCapEnabled,
        },
      },
    };
  },

  upsertFlatUserCap: ({ input }) => {
    const c = caps();
    c.flatUserCap = input.flatUserCap;
    c.flatUserCapEnabled = input.flatUserCapEnabled;
    saveCaps(c);
    return {
      upsertFlatUserCap: {
        __typename: 'UpsertFlatUserCapPayload',
        flatUserCap: c.flatUserCap,
        flatUserCapEnabled: c.flatUserCapEnabled,
        errors: [],
      },
    };
  },

  getUserOverrides: () => {
    const c = caps();
    const nodes = Object.entries(c.overrides).map(([gid, o]) => {
      const u = USERS.find((x) => x.gid === gid);
      return {
        __typename: 'GitlabSubscriptionBudgetCapUserOverride',
        cap: o.cap,
        capEnabled: o.enabled,
        user: toGqlUser(u),
      };
    });
    return {
      subscriptionUsage: {
        __typename: 'GitlabSubscriptionUsage',
        budgetCaps: {
          __typename: 'GitlabSubscriptionBudgetCaps',
          userOverrides: {
            __typename: 'GitlabSubscriptionBudgetCapUserOverrideConnection',
            nodes,
            pageInfo: { ...PAGE_INFO(false), startCursor: null, endCursor: null },
          },
        },
      },
    };
  },

  upsertUserBudgetCapOverrides: ({ overrides }) => {
    const c = caps();
    overrides.forEach((o) => {
      c.overrides[o.userId] = { cap: o.cap, enabled: o.enabled };
    });
    saveCaps(c);
    return {
      upsertUserBudgetCapOverrides: {
        __typename: 'UpsertUserBudgetCapOverridesPayload',
        userOverrides: overrides.map((o) => ({
          __typename: 'GitlabSubscriptionBudgetCapUserOverride',
          cap: o.cap,
          capEnabled: o.enabled,
          user: { __typename: 'User', id: o.userId },
        })),
        errors: [],
      },
    };
  },

  groupUsersSearch: ({ search = '' }) => {
    const q = search.toLowerCase();
    const matches = USERS.filter(
      (u) => u.entityType === 'user' && (u.name.toLowerCase().includes(q) || u.username.includes(q)),
    ).slice(0, 20);
    return {
      namespace: {
        __typename: 'Group',
        id: 'gid://gitlab/Group/101',
        users: {
          __typename: 'GroupMemberConnection',
          nodes: matches.map((u) => ({ __typename: 'GroupMember', id: `gid://gitlab/GroupMember/${u.id}`, user: toGqlUser(u) })),
          pageInfo: { __typename: 'PageInfo', hasNextPage: false, endCursor: null, startCursor: null },
        },
      },
    };
  },
});

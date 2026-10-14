// Synthetic data for GitLab's personal homepage (start page of the demo).
const U = 'gid://gitlab/User/4242';
const ago = (h) => new Date(Date.now() - h * 3600e3).toISOString();
const conn = (count) => ({ __typename: 'Connection', count, nodes: count ? [{ __typename: 'Node', id: `gid://x/${count}`, updatedAt: ago(3) }] : [] });

const wi = (id, title, type, icon, path, h) => ({
  __typename: 'RecentlyViewedItem',
  viewedAt: ago(h),
  item: {
    __typename: 'WorkItem',
    id: `gid://gitlab/WorkItem/${id}`,
    title,
    webUrl: `https://gitlab.com/${path}`,
    workItemType: { __typename: 'WorkItemType', id: `gid://gitlab/WorkItems::Type/${type}`, name: type, iconName: icon },
  },
});
const mr = (id, title, path, h) => ({
  __typename: 'RecentlyViewedItem',
  viewedAt: ago(h),
  item: { __typename: 'MergeRequest', id: `gid://gitlab/MergeRequest/${id}`, title, webUrl: `https://gitlab.com/${path}` },
});

export const homeResolvers = {
  MergeRequestsWidgetMetadata: () => ({
    currentUser: {
      __typename: 'CurrentUser',
      id: U,
      reviewRequestedMergeRequests: { ...conn(1), __typename: 'MergeRequestConnection' },
      assignedMergeRequests: { ...conn(2), __typename: 'MergeRequestConnection' },
    },
  }),
  WorkItemsWidgetMetadata: () => ({
    currentUser: {
      __typename: 'CurrentUser',
      id: U,
      assigned: { ...conn(4), __typename: 'WorkItemConnection' },
      authored: { ...conn(6), __typename: 'WorkItemConnection' },
    },
  }),
  UserStatus: () => ({
    currentUser: { __typename: 'CurrentUser', id: U, status: null },
  }),
  todos: () => ({
    currentUser: {
      __typename: 'CurrentUser',
      id: U,
      todos: {
        __typename: 'TodoConnection',
        nodes: [],
        pageInfo: { __typename: 'PageInfo', hasNextPage: false, hasPreviousPage: false, startCursor: null, endCursor: null },
      },
    },
  }),
  RecentlyViewedItemsEE: () => ({
    currentUser: {
      __typename: 'CurrentUser',
      id: U,
      recentlyViewedItems: [
        mr(9101, 'Add retry with backoff to webhook dispatcher', 'acme-corp/platform/api/-/merge_requests/482', 1),
        wi(7712, 'Checkout flow times out for large carts', 'Issue', 'work-item-issue', 'acme-corp/storefront/web/-/work_items/1287', 3),
        wi(7710, 'Q4 platform reliability', 'Epic', 'work-item-epic', 'groups/acme-corp/-/epics/61', 20),
        mr(9088, 'Migrate CI to reusable components', 'acme-corp/platform/api/-/merge_requests/476', 26),
      ],
    },
  }),
};

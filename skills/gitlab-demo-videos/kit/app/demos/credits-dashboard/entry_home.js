// Start page: GitLab's real personal homepage app (app/assets/javascripts/homepage),
// fed by the in-browser mock GraphQL resolvers in ./home_data.js.
import '@demo/src/shell/boot';
import Vue from 'vue';
import VueApollo from 'vue-apollo';
import HomepageApp from '~/homepage/components/homepage_app.vue';
import { createMockApolloClient } from '@demo/src/shell/mock_apollo';
import { homeResolvers } from './home_data';

Vue.use(VueApollo);
const el = document.getElementById('js-homepage-app');
// eslint-disable-next-line no-new
new Vue({
  el,
  name: 'HomepageAppRoot',
  provide: { duoCodeReviewBotUsername: 'GitLabDuo' },
  apolloProvider: new VueApollo({ defaultClient: createMockApolloClient(homeResolvers, { latency: 150 }) }),
  render: (h) =>
    h(HomepageApp, {
      props: {
        reviewRequestedPath: '/dashboard/merge_requests?reviewer_username=arivera',
        activityPath: '/users/arivera/activity',
        assignedMergeRequestsPath: '/dashboard/merge_requests?assignee_username=arivera',
        assignedWorkItemsPath: '/dashboard/work_items?assignee_username=arivera',
        authoredWorkItemsPath: '/dashboard/work_items?author_username=arivera',
        lastPushEvent: null,
      },
    }),
});

// Smoke: a tiny Vue page that talks to "GitLab" through GitLab's own default Apollo client and axios,
// answered by mockBackend in the browser.
import { mockBackend } from '@demo/src/shell/boot';
import Vue from 'vue';
import VueApollo from 'vue-apollo';
import gql from 'graphql-tag';
import createDefaultClient from '~/lib/graphql';
import axios from '~/lib/utils/axios_utils';
import PageHeading from '~/vue_shared/components/page_heading.vue';
import { GlTableLite, GlToggle, GlBadge } from '@gitlab/ui';

mockBackend.graphql({
  smokeTriggers: () => ({
    project: {
      __typename: 'Project',
      id: 'gid://gitlab/Project/2001',
      aiFlowTriggers: {
        __typename: 'AiFlowTriggerConnection',
        nodes: [
          { __typename: 'AiFlowTrigger', id: 'gid://gitlab/Ai::FlowTrigger/1', description: 'Review every new merge request', active: true },
          { __typename: 'AiFlowTrigger', id: 'gid://gitlab/Ai::FlowTrigger/2', description: 'Nightly dependency review', active: true },
        ],
      },
    },
  }),
});
mockBackend.rest({ 'GET /api/v4/projects/:id': ({ params }) => ({ id: Number(params.id), name: 'checkout-service' }) });

Vue.use(VueApollo);
const apolloProvider = new VueApollo({ defaultClient: createDefaultClient() });

// eslint-disable-next-line no-new
new Vue({
  el: '#js-smoke-app',
  apolloProvider,
  data: () => ({ triggers: [], restName: '' }),
  apollo: {
    triggers: {
      query: gql`query smokeTriggers { project(fullPath: "acme-corp/checkout-service") { id aiFlowTriggers { nodes { id description active } } } }`,
      update: (d) => d.project.aiFlowTriggers.nodes,
    },
  },
  async mounted() {
    const { data } = await axios.get('/api/v4/projects/2001');
    this.restName = data.name;
  },
  render(h) {
    return h('div', [
      h(PageHeading, { props: { heading: 'Flow triggers' } }, [h('template', { slot: 'description' }, `Shell smoke page (REST says: ${this.restName || '...'})`)]),
      h(GlTableLite, {
        props: { items: this.triggers, fields: [{ key: 'description', label: 'Description' }, { key: 'active', label: 'Status' }] },
        scopedSlots: {
          'cell(active)': ({ item }) => h('div', { class: 'gl-flex gl-gap-3 gl-items-center' }, [h(GlToggle, { props: { value: item.active, label: 'Active', labelPosition: 'hidden' } }), h(GlBadge, { props: { variant: 'success' } }, 'Active')]),
        },
      }),
    ]);
  },
});

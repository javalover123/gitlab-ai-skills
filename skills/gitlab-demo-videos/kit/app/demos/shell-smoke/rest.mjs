// Full-page form posts of the smoke demo (Rails _method is honoured by harness/serve.mjs).
export default {
  'PATCH /groups/acme-corp': () => ({ redirect: '/groups/acme-corp/-/edit#js-permissions-settings', flash: { notice: "Group 'Acme Corp' was successfully updated." } }),
  'PATCH /acme-corp/checkout-service/-/settings/merge_requests': () => ({
    redirect: '/acme-corp/checkout-service/-/settings/merge_requests',
    flash: { notice: "Project 'checkout-service' was successfully updated." },
  }),
};

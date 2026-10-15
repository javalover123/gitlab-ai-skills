// Smoke demo for the shared shell: group / project / admin panels, HAML helpers, form POST + flash,
// mockBackend (GraphQL via GitLab's default client + axios REST). Not a customer video.
import { settingsBlock, settingsSection, checkbox, saveButton, form, helpLink } from '../../src/shell/haml.mjs';

const G = 'acme-corp';
const P = 'acme-corp/checkout-service';

// ee/app/views/groups/settings/_gitlab_credits_dashboard.html.haml (inside groups/settings/_permissions)
const permissionsBody = form({
  action: '/groups/acme-corp',
  cls: 'gl-show-field-errors js-general-permissions-form',
  body: `<input type="hidden" name="update_section" value="js-permissions-settings">
<fieldset>
<h5>Permissions</h5>
<div class="form-group gl-mb-3">${checkbox({ name: 'group[share_with_group_lock]', label: 'Projects in <a href="/acme-corp">Acme Corp</a> cannot be shared with other groups', helpText: 'Prevents sharing a project in this group with another group.' })}</div>
<div class="form-group gl-mb-3">${checkbox({ name: 'group[mentions_disabled]', label: 'Group mentions are disabled', helpText: 'Group members are not notified if the group is mentioned.' })}</div>
</fieldset>
<div class="form-group">
<h5>GitLab Credits dashboard</h5>
${checkbox({ name: 'group[display_gitlab_credits_user_data]', label: 'Display user data', helpText: 'If selected, individual usernames and their credit usage are visible on the GitLab Credits dashboard. If your organization needs to restrict access to individual user activity for compliance or privacy reasons, clear this checkbox.' })}
</div>
${saveButton()}`,
});

export default [
  {
    route: `/groups/${G}/-/edit`,
    name: 'group-edit',
    group: G,
    activeMenuId: 'general',
    settingsLayout: true,
    title: ['General settings'],
    crumbs: [{ text: 'General settings', href: `/groups/${G}/-/edit` }],
    bodyPage: 'groups:edit',
    pageStyles: ['page_bundles_group_edit.css'],
    content: `<h1 class="gl-sr-only">General settings</h1>
${settingsBlock({
  heading: 'Naming, description, visibility',
  id: 'js-general-settings',
  testid: 'general-settings',
  expanded: true,
  description: `Update your group name, description, avatar, and visibility. ${helpLink('Learn more about groups.', '/help/user/group/_index.md')}`,
  body: `<div class="form-group gl-form-group"><label class="gl-block col-form-label" for="group_name">Group name</label><input class="gl-form-input form-control gl-form-input-xl" id="group_name" value="Acme Corp"></div>`,
})}
${settingsBlock({
  heading: 'Permissions and group features',
  id: 'js-permissions-settings',
  testid: 'permissions-settings',
  description: 'Configure advanced permissions, Large File Storage, two-factor authentication, and customer relations settings.',
  body: permissionsBody,
})}
${settingsBlock({ heading: 'Advanced', id: 'js-advanced-settings', description: 'Perform advanced options such as changing path, transferring, exporting, or deleting the group.' })}`,
  },
  {
    route: `/${P}/-/settings/merge_requests`,
    name: 'project-mr-settings',
    project: P,
    activeMenuId: 'merge_request_settings',
    settingsLayout: true,
    title: ['Merge requests'],
    crumbs: [
      { text: 'Settings', href: `/${P}/-/settings/merge_requests` },
      { text: 'Merge requests', href: `/${P}/-/settings/merge_requests` },
    ],
    bodyPage: 'projects:settings:merge_requests:show',
    content: settingsSection({
      heading: 'GitLab Duo Code Review',
      id: 'merge-request-duo-code-review-settings',
      cls: 'merge-requests-feature',
      body: form({
        action: `/${P}/-/settings/merge_requests`,
        body: `<div class="form-group">${checkbox({ name: 'project[project_setting_attributes][auto_duo_code_review_enabled]', label: 'Enable automatic reviews by GitLab Duo', helpText: 'GitLab Duo reviews new merge requests immediately, unless they are drafts or contain no changes.' })}</div>
${saveButton()}`,
      }),
    }),
  },
  {
    route: `/${P}/-/automate/*`,
    routes: [`/${P}/-/automate`],
    name: 'project-automate',
    project: P,
    activeMenuId: 'ai_flow_triggers',
    title: ['Triggers', 'AI'],
    crumbs: [{ text: 'Triggers', href: `/${P}/-/automate/triggers` }],
    bodyPage: 'projects:duo_agents_platform:show',
    entry: 'entry_automate.js',
    content: '<div id="js-smoke-app"></div>',
  },
  {
    route: '/admin/gitlab_duo',
    name: 'admin-duo',
    panel: 'admin',
    activeMenuId: 'duo_settings_menu',
    title: ['GitLab Duo', 'Admin area'],
    breadcrumbs: [{ text: 'Admin area', href: '/admin' }, { text: 'GitLab Duo', href: '/admin/gitlab_duo' }],
    bodyPage: 'admin:gitlab_duo:show',
    content: '<h1 class="page-title gl-text-size-h-display">GitLab Duo</h1><p class="gl-text-subtle">Admin panel smoke page.</p>',
  },
];

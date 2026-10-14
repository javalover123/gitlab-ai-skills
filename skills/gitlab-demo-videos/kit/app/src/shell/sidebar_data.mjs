// Builds the `data-sidebar` JSON that GitLab's SidebarsHelper#super_sidebar_context renders
// server-side (app/helpers/sidebars_helper.rb + ee/app/helpers/ee/sidebars_helper.rb, v19.4.1-ee).
//
// Panels:
//   your_work  lib/sidebars/your_work/**
//   profile    lib/sidebars/user_settings/** (+ ee)
//   group      Sidebars::Groups::SuperSidebarPanel  (lib/sidebars/groups/**, ee/lib/{ee/,}sidebars/groups/**)
//   project    Sidebars::Projects::SuperSidebarPanel (lib/sidebars/projects/**, ee/lib/{ee/,}sidebars/projects/**)
//   admin      Sidebars::Admin::Panel (ee/lib/ee/sidebars/admin/panel.rb) - Self-Managed/Dedicated administrator
//
// Group/project menus reproduce the super sidebar transform: old menu items are moved into the
// super-sidebar sections by `super_sidebar_parent`, ordered by each section's NilMenuItem placeholders,
// with non-placeholder items appended. What renders is what a top-level group Owner on GitLab.com
// (Ultimate, GitLab Duo Agent Platform on) sees; conditions that are feature-flagged off by default at
// v19.4.1 (e.g. ai_catalog_mcp_servers, secrets_manager_paid_experience, observability) are left out.
//
// Item ids are the Rails `item_id`s - use them as `activeMenuId` in pages.mjs (see ITEM_IDS below).

import { resolveGroup, resolveProject } from './contexts.mjs';

const item = (id, title, link, extra = {}) => ({ id, title, link, is_active: false, ...extra });
const section = (id, title, icon, items, extra = {}) => ({
  id,
  title,
  icon,
  link: items.find((i) => !i.link_classes)?.link || items[0]?.link,
  is_active: false,
  items,
  separated: false,
  ...extra,
});
const menu = (id, title, icon, link, extra = {}) => ({
  id,
  title,
  icon,
  link,
  is_active: false,
  items: [],
  separated: false,
  ...extra,
});
const HIDDEN = 'js-super-sidebar-nav-item-hidden';

// ---------------------------------------------------------------------------------------------
// Your work / User settings (static)
// ---------------------------------------------------------------------------------------------
const yourWork = () => ({
  header: 'Your work',
  items: [
    menu('homepage_menu', 'Home', 'home', '/'),
    menu('projects_menu', 'Projects', 'project', '/dashboard/projects'),
    menu('groups_menu', 'Groups', 'group', '/dashboard/groups'),
    menu('issues_menu', 'Work items', 'work-items', '/dashboard/work_items?assignee_username=arivera', {
      pill_count: '4',
      pill_count_field: 'assigned_issues',
    }),
    menu('merge_requests_menu', 'Merge requests', 'merge-request', '/dashboard/merge_requests', {
      pill_count: '3',
      pill_count_field: 'total_merge_requests',
    }),
    menu('todos_menu', 'To-Do List', 'todo-done', '/dashboard/todos', {
      pill_count: '0',
      pill_count_field: 'todos',
    }),
    menu('milestones_menu', 'Milestones', 'milestone', '/dashboard/milestones'),
    menu('snippets_menu', 'Snippets', 'snippet', '/dashboard/snippets'),
    menu('activity_menu', 'Activity', 'history', '/dashboard/activity'),
    menu('import_history_menu', 'Import history', 'import', '/import/history'),
  ],
});

const profile = () => ({
  header: 'User settings',
  items: [
    menu('profile_menu', 'Profile', 'profile', '/-/user_settings/profile'),
    menu('account_menu', 'Account', 'account', '/-/profile/account'),
    menu('profile_billing_menu', 'Billing', 'credit-card', '/-/profile/billings'),
    menu('access_menu', 'Access', 'key', '/-/profile/two_factor_auth', {
      items: [
        ['password_and_authentication', 'Password and authentication', '/-/profile/two_factor_auth'],
        ['access_tokens', 'Personal access tokens', '/-/user_settings/personal_access_tokens'],
        ['ssh_keys', 'SSH keys', '/-/user_settings/ssh_keys'],
        ['gpg_keys', 'GPG keys', '/-/user_settings/gpg_keys'],
        ['applications', 'Applications', '/-/user_settings/applications'],
        ['active_sessions', 'Active sessions', '/-/user_settings/active_sessions'],
        ['authentication_log', 'Authentication log', '/-/user_settings/authentication_log'],
      ].map(([id, title, link]) => ({ id, title, link, is_active: false })),
    }),
    menu('chat_menu', 'Integration accounts', 'connected', '/-/user_settings/integration_accounts'),
    menu('emails_menu', 'Emails', 'mail', '/-/profile/emails'),
    menu('notifications_menu', 'Notifications', 'notifications', '/-/profile/notifications'),
    menu('preferences_menu', 'Preferences', 'preferences', '/-/profile/preferences'),
    menu('comment_templates_menu', 'Comment templates', 'comment-lines', '/-/profile/comment_templates'),
    menu('usage_quotas_menu', 'Usage quotas', 'quota', '/-/profile/usage_quotas'),
    menu('gitlab_credits_dashboard_menu', 'GitLab Credits', 'gitlab-credits', '/-/profile/gitlab_credits_dashboard'),
  ],
});

// ---------------------------------------------------------------------------------------------
// Group (Sidebars::Groups::SuperSidebarPanel)
// ---------------------------------------------------------------------------------------------
// opts: { duoFeaturesEnabled = true, plan (defaults to group.plan), crm = false }
function groupPanel(g, opts = {}) {
  const root = !g.parent;
  const ultimate = (opts.plan || g.plan || 'ultimate') === 'ultimate';
  const duo = opts.duoFeaturesEnabled !== false;
  const G = (rest) => `/groups/${g.fullPath}/-/${rest}`;
  const U = (x) => (ultimate ? [x] : []); // Ultimate-only items
  const R = (x) => (root ? [x] : []); // top-level-group-only items

  const items = [
    // Sidebars::StaticMenu <- Groups::Menus::ScopeMenu
    item('group_overview', g.name, `/${g.fullPath}`, { avatar: g.avatarUrl || null, entity_id: g.id }),
    section('manage_menu', 'Manage', 'users', [
      item('activity', 'Activity', G('activity')),
      item('members', 'Members', G('group_members')),
      item('labels', 'Labels', G('labels')),
      item('achievements', 'Achievements', G('achievements')),
    ]),
    section('plan_menu', 'Plan', 'planning', [
      item('group_issue_list', 'Work items', G('work_items'), { pill_count_field: 'openWorkItemsCount' }),
      item('group_epic_list', 'Work items', G('work_items'), { link_classes: HIDDEN }),
      item('issue_boards', 'Issue boards', G('boards')),
      item('epic_boards', 'Epic boards', G('epic_boards')),
      item('roadmap', 'Roadmap', G('roadmap')),
      item('milestones', 'Milestones', G('milestones')),
      item('iterations', 'Iterations', G('cadences')),
      item('group_wiki', 'Wiki', G('wikis/home')),
      ...(opts.crm ? [item('crm_contacts', 'Customer relations', G('crm/contacts'))] : []),
    ]),
    // EE: DuoAgentsMenu inserted after PlanMenu for top-level groups only
    ...(root && duo
      ? [
          section('duo_agents_menu', 'AI', 'tanuki-ai', [
            item('ai_agents', 'Agents', G('automate/agents')),
            item('ai_flows', 'Flows', G('automate/flows')),
          ]),
        ]
      : []),
    section('code_menu', 'Code', 'code', [
      item('group_merge_request_list', 'Merge requests', G('merge_requests'), { pill_count_field: 'openMergeRequestsCount' }),
    ]),
    section('build_menu', 'Build', 'rocket', [item('runners', 'Runners', G('runners'))]),
    section('secure_menu', 'Secure', 'shield', [
      ...U(item('security_dashboard', 'Security dashboard', G('security/dashboard'))),
      ...U(item('vulnerability_report', 'Vulnerability report', G('security/vulnerabilities'))),
      ...U(item('security_inventory', 'Security inventory', G('security/inventory'))),
      ...U(item('dependency_list', 'Dependency list', G('dependencies'))),
      item('audit_events', 'Audit events', G('audit_events')),
      ...U(item('compliance', 'Compliance center', G('security/compliance_dashboard'))),
      ...U(item('scan_policies', 'Policies', G('security/policies'))),
      ...U(item('configuration', 'Security configuration', G('security/configuration'))),
    ]),
    section('deploy_menu', 'Deploy', 'deployments', [
      item('packages_registry', 'Package registry', G('packages')),
      item('container_registry', 'Container registry', G('container_registries')),
    ]),
    section('operations_menu', 'Operate', 'cloud-pod', [
      item('dependency_proxy', 'Dependency Proxy', G('dependency_proxy')),
      item('group_kubernetes_clusters', 'Kubernetes', G('clusters')),
      item('infrastructure_registry', 'Terraform modules', G('infrastructure_registry')),
    ]),
    section('analyze_menu', 'Analyze', 'chart', [
      ...U(item('analytics_dashboards', 'Analytics dashboards', G('analytics/dashboards'))),
      item('cycle_analytics', 'Value stream analytics', G('analytics/value_stream_analytics')),
      item('ci_cd_analytics', 'CI/CD analytics', G('analytics/ci_cd')),
      item('contribution_analytics', 'Contribution analytics', G('contribution_analytics')),
      ...U(item('devops_adoption', 'DevOps adoption', G('analytics/devops_adoption'))),
      ...U(item('insights', 'Insights', G('insights/'))),
      item('issues_analytics', 'Issue analytics', G('issues_analytics')),
      item('productivity_analytics', 'Productivity analytics', G('analytics/productivity_analytics')),
      item('repository_analytics', 'Repository analytics', G('analytics/repository_analytics')),
    ]),
    // Groups::Menus::SettingsMenu (+ EE SettingsMenu#add_admin_group_settings_menu_items)
    section(
      'settings_menu',
      'Settings',
      'settings',
      [
        item('general', 'General', G('edit')),
        ...R(item('service_accounts', 'Service accounts', G('settings/service_accounts'))),
        ...R(item('roles_and_permissions', 'Roles and permissions', G('settings/roles_and_permissions'))),
        item('integrations', 'Integrations', G('settings/integrations')),
        item('webhooks', 'Webhooks', G('hooks')),
        item('access_tokens', 'Access tokens', G('settings/access_tokens')),
        item('group_work_items_settings', 'Work items', G('settings/work_items')),
        item('repository', 'Repository', G('settings/repository')),
        item('ci_cd', 'CI/CD', G('settings/ci_cd')),
        item('analytics', 'Analytics', G('settings/analytics')),
        item('applications', 'Applications', G('settings/applications')),
        item('packages_and_registries', 'Packages and registries', G('settings/packages_and_registries')),
        ...R(item('usage_quotas', 'Usage quotas', G('usage_quotas'))),
        ...R(item('gitlab_duo_settings', 'GitLab Duo', G('settings/gitlab_duo'))),
        ...R(item('gitlab_credits_dashboard', 'GitLab Credits', G('settings/gitlab_credits_dashboard'))),
        ...(root && duo ? [item('governance', 'Governance', G('settings/gitlab_duo/governance'))] : []),
        ...R(item('saml_sso', 'SAML SSO', G('saml'))),
        ...R(item('domain_verification', 'Domain Verification', G('settings/domain_verification'))),
        item('billing', 'Billing', G('billings')),
        ...(root && ultimate ? [item('reporting', 'Reporting', G('settings/reporting'))] : []),
        item('workspaces_settings', 'Workspaces', G('settings/workspaces')),
      ],
      { separated: true },
    ),
  ];
  return {
    header: 'Group',
    items,
    // SidebarsHelper#super_sidebar_default_pins('group') + EE (group_epic_list dropped when group_issue_list pinned)
    pins: ['group_overview', 'members', 'group_issue_list', 'issue_boards', 'group_merge_request_list', 'epic_boards'],
    currentContext: {
      namespace: 'groups',
      item: { id: g.id, name: g.name, namespace: g.fullName, fullPath: g.fullPath, webUrl: `/${g.fullPath}`, avatarUrl: g.avatarUrl || null },
    },
  };
}

// ---------------------------------------------------------------------------------------------
// Project (Sidebars::Projects::SuperSidebarPanel)
// ---------------------------------------------------------------------------------------------
// opts: { duoFeaturesEnabled = true, duoWorkflowEnabled = true (Sessions), plan = 'ultimate' }
function projectPanel(p, opts = {}) {
  const ultimate = (opts.plan || p.plan || 'ultimate') === 'ultimate';
  const duo = opts.duoFeaturesEnabled !== false;
  const P = (rest) => `/${p.fullPath}/-/${rest}`;
  const U = (x) => (ultimate ? [x] : []);
  const b = p.defaultBranch || 'main';

  const items = [
    item('project_overview', p.name, `/${p.fullPath}`, { avatar: p.avatarUrl || null, entity_id: p.id }),
    section('manage_menu', 'Manage', 'users', [
      item('activity', 'Activity', `/${p.fullPath}/activity`),
      item('members', 'Members', P('project_members')),
      item('labels', 'Labels', P('labels')),
    ]),
    section('plan_menu', 'Plan', 'planning', [
      item('project_issue_list', 'Work items', P('work_items'), { pill_count_field: 'openWorkItemsCount' }),
      item('boards', 'Issue boards', P('boards')),
      item('milestones', 'Milestones', P('milestones')),
      item('iterations', 'Iterations', P('cadences')),
      item('project_wiki', 'Wiki', P('wikis/home')),
      ...U(item('requirements', 'Requirements', P('requirements_management/requirements'))),
    ]),
    // EE: DuoAgentsMenu inserted after PlanMenu (ee/lib/sidebars/projects/super_sidebar_menus/duo_agents_menu.rb)
    ...(duo
      ? [
          section('duo_agents_menu', 'AI', 'tanuki-ai', [
            item('ai_catalog_agents', 'Agents', P('automate/agents')),
            item('ai_flows', 'Flows', P('automate/flows')),
            item('ai_flow_triggers', 'Triggers', P('automate/triggers')),
            ...(opts.duoWorkflowEnabled !== false ? [item('agents_runs', 'Sessions', P('automate/agent-sessions'))] : []),
          ]),
        ]
      : []),
    section('code_menu', 'Code', 'code', [
      item('project_merge_request_list', 'Merge requests', P('merge_requests'), { pill_count_field: 'openMergeRequestsCount' }),
      item('files', 'Repository', P(`tree/${b}`)),
      item('branches', 'Branches', P('branches')),
      item('commits', 'Commits', P(`commits/${b}?ref_type=heads`)),
      item('tags', 'Tags', P('tags')),
      item('graphs', 'Repository graph', P(`network/${b}?ref_type=heads`)),
      item('compare', 'Compare revisions', P(`compare?from=${b}&to=${b}`)),
      item('project_snippets', 'Snippets', P('snippets')),
      item('file_locks', 'Locked files', `/${p.fullPath}/path_locks`),
    ]),
    section('build_menu', 'Build', 'rocket', [
      item('pipelines', 'Pipelines', P('pipelines')),
      item('jobs', 'Jobs', P('jobs')),
      item('pipelines_editor', 'Pipeline editor', P(`ci/editor?branch_name=${b}`)),
      item('pipeline_schedules', 'Pipeline schedules', P('pipeline_schedules')),
      ...U(item('test_cases', 'Test cases', P('quality/test_cases'))),
      item('artifacts', 'Artifacts', P('artifacts')),
    ]),
    section('secure_menu', 'Secure', 'shield', [
      ...U(item('dashboard', 'Security dashboard', P('security/dashboard'))),
      ...U(item('vulnerability_report', 'Vulnerability report', P('security/vulnerability_report'))),
      ...U(item('dependency_list', 'Dependency list', P('dependencies'))),
      item('audit_events', 'Audit events', P('audit_events')),
      ...U(item('compliance', 'Compliance center', P('security/compliance_dashboard'))),
      ...U(item('scan_policies', 'Policies', P('security/policies'))),
      ...U(item('on_demand_scans', 'On-demand scans', P('on_demand_scans'))),
      item('configuration', 'Security configuration', P('security/configuration')),
    ]),
    section('deploy_menu', 'Deploy', 'deployments', [
      item('releases', 'Releases', P('releases')),
      item('feature_flags', 'Feature flags', P('feature_flags')),
      item('packages_registry', 'Package registry', P('packages')),
      item('container_registry', 'Container registry', `/${p.fullPath}/container_registry`),
      item('model_registry', 'Model registry', P('ml/models')),
      item('pages', 'Pages', `/${p.fullPath}/pages`),
    ]),
    section('operations_menu', 'Operate', 'cloud-pod', [
      item('environments', 'Environments', P('environments')),
      item('kubernetes', 'Kubernetes clusters', P('clusters')),
      item('terraform_states', 'Terraform states', P('terraform')),
      item('infrastructure_registry', 'Terraform modules', P('terraform_module_registry')),
    ]),
    section('monitor_menu', 'Monitor', 'monitor', [
      item('error_tracking', 'Error Tracking', P('error_tracking')),
      item('alert_management', 'Alerts', P('alert_management')),
      item('incidents', 'Incidents', P('incidents')),
      item('on_call_schedules', 'On-call Schedules', P('oncall_schedules')),
      item('escalation_policies', 'Escalation Policies', P('escalation_policies')),
      item('service_desk', 'Service Desk', P('issues/service_desk')),
    ]),
    section('analyze_menu', 'Analyze', 'chart', [
      ...U(item('dashboards_analytics', 'Analytics dashboards', P('analytics/dashboards'))),
      item('cycle_analytics', 'Value stream analytics', P('value_stream_analytics')),
      item('contributors', 'Contributor analytics', P(`graphs/${b}?ref_type=heads`)),
      item('ci_cd_analytics', 'CI/CD analytics', P('pipelines/charts')),
      item('repository_analytics', 'Repository analytics', P(`graphs/${b}/charts`)),
      item('code_review', 'Code review analytics', P('analytics/code_reviews')),
      item('issues', 'Issue analytics', P('analytics/issues_analytics')),
      ...U(item('insights', 'Insights', `/${p.fullPath}/insights/`)),
      item('model_experiments', 'Model experiments', P('ml/experiments')),
    ]),
    // Projects::Menus::SettingsMenu::MENU_ITEMS (+ EE work items after CI/CD)
    section(
      'settings_menu',
      'Settings',
      'settings',
      [
        item('general', 'General', `/${p.fullPath}/edit`),
        item('service_accounts', 'Service accounts', P('settings/service_accounts')),
        item('integrations', 'Integrations', P('settings/integrations')),
        item('webhooks', 'Webhooks', P('hooks')),
        item('access_tokens', 'Access tokens', P('settings/access_tokens')),
        item('repository', 'Repository', P('settings/repository')),
        item('merge_request_settings', 'Merge requests', P('settings/merge_requests')),
        item('ci_cd', 'CI/CD', P('settings/ci_cd')),
        item('work_items', 'Work items', P('settings/work_items')),
        item('packages_and_registries', 'Packages and registries', P('settings/packages_and_registries')),
        item('monitor', 'Monitor', P('settings/operations')),
        item('usage_quotas', 'Usage quotas', P('usage_quotas')),
      ],
      { separated: true },
    ),
  ];
  return {
    header: 'Project',
    items,
    // SidebarsHelper#super_sidebar_default_pins('project')
    pins: ['project_overview', 'members', 'project_issue_list', 'branches', 'project_merge_request_list', 'pipelines'],
    currentContext: {
      namespace: 'projects',
      item: { id: p.id, name: p.name, namespace: p.fullName, fullPath: p.fullPath, webUrl: `/${p.fullPath}`, avatarUrl: p.avatarUrl || null },
    },
  };
}

// ---------------------------------------------------------------------------------------------
// Admin (Self-Managed / Dedicated administrator) - ee/lib/ee/sidebars/admin/panel.rb
// ---------------------------------------------------------------------------------------------
function adminPanel() {
  const A = (rest = '') => `/admin${rest ? `/${rest}` : ''}`;
  const S = (rest) => A(`application_settings/${rest}`);
  return {
    header: 'Admin area',
    items: [
      menu('admin_overview_menu', 'Instance overview', 'overview', A(), {
        items: [
          item('dashboard', 'Dashboard', A()),
          item('projects', 'Projects', A('projects')),
          item('users', 'Users', A('users')),
          item('groups', 'Groups', A('groups')),
          item('organizations', 'Organizations', A('organizations')),
          item('topics', 'Topics', A('topics')),
          item('gitaly_servers', 'Gitaly servers', A('gitaly_servers')),
        ],
      }),
      menu('ci_cd_menu', 'CI/CD', 'rocket', A('runners'), {
        items: [item('runners', 'Runners', A('runners')), item('jobs', 'Jobs', A('jobs'))],
      }),
      menu('analytics_menu', 'Analytics', 'chart', A('dev_ops_reports'), {
        items: [item('dev_ops_reports', 'DevOps adoption', A('dev_ops_reports')), item('usage_trends', 'Usage trends', A('usage_trends'))],
      }),
      menu('monitoring_menu', 'Monitoring', 'monitor', A('system_info'), {
        items: [
          item('system_info', 'System information', A('system_info')),
          item('background_migrations', 'Background migrations', A('background_migrations')),
          item('background_jobs', 'Background jobs', A('background_jobs')),
          item('health_check', 'Health check', A('health_check')),
          item('audit_logs', 'Audit events', A('audit_logs')),
          item('database_diagnostics', 'Database diagnostics', A('database_diagnostics')),
        ],
      }),
      menu('messages_menu', 'Messages', 'bullhorn', A('broadcast_messages'), {
        items: [
          item('broadcast_messages', 'Broadcast Messages', A('broadcast_messages')),
          item('targeted_messages', 'Targeted Messages', A('targeted_messages')),
        ],
      }),
      menu('system_hooks_menu', 'System hooks', 'hook', A('hooks')),
      menu('applications_menu', 'Applications', 'applications', A('applications')),
      menu('abuse_reports_menu', 'Abuse reports', 'slight-frown', A('abuse_reports')),
      menu('subscription_menu', 'Subscription', 'license', A('subscription')),
      menu('duo_settings_menu', 'GitLab Duo', 'tanuki-ai', A('gitlab_duo')),
      menu('gitlab_credits_dashboard_menu', 'GitLab Credits', 'gitlab-credits', A('gitlab_credits_dashboard')),
      menu('kubernetes_menu', 'Kubernetes', 'cloud-gear', A('clusters')),
      menu('spam_logs_menu', 'Spam logs', 'spam', A('spam_logs')),
      menu('push_rules_menu', 'Push rules', 'push-rules', A('push_rule')),
      menu('geo_menu', 'Geo', 'location-dot', A('geo/sites'), {
        items: [item('geo_nodes', 'Sites', A('geo/sites')), item('geo_settings', 'Settings', A('geo/settings'))],
      }),
      menu('deploy_keys_menu', 'Deploy keys', 'key', A('deploy_keys')),
      menu('credentials_menu', 'Credentials', 'lock', A('credentials')),
      menu('labels_menu', 'Labels', 'labels', A('labels')),
      menu('admin_settings_menu', 'Settings', 'settings', S('general'), {
        separated: true,
        items: [
          item('general_settings', 'General', S('general')),
          item('service_accounts', 'Service accounts', S('service_accounts')),
          item('roles_and_permissions', 'Roles and permissions', S('roles_and_permissions')),
          item('search', 'Search', S('search')),
          item('admin_integrations', 'Integrations', S('integrations')),
          item('admin_repository', 'Repository', S('repository')),
          item('admin_ci_cd', 'CI/CD', S('ci_cd')),
          item('admin_security_and_compliance', 'Security and compliance', S('security_and_compliance')),
          item('work_item_settings', 'Work items', S('work_item')),
          item('admin_reporting', 'Reporting', S('reporting')),
          item('admin_templates', 'Templates', S('templates')),
          item('admin_metrics', 'Metrics and profiling', S('metrics_and_profiling')),
          item('admin_network', 'Network', S('network')),
          item('admin_appearance', 'Appearance', S('appearance')),
          item('admin_preferences', 'Preferences', S('preferences')),
          item('admin_usage_quotas', 'Usage quotas', S('usage_quotas')),
        ],
      }),
    ],
    pins: [],
    currentContext: {},
  };
}

function panelFor({ panel, group, project, sidebar = {} }) {
  switch (panel) {
    case 'your_work':
      return { ...yourWork(), pins: [], currentContext: {} };
    case 'profile':
      return { ...profile(), pins: [], currentContext: {} };
    case 'group':
      return groupPanel(resolveGroup(group), sidebar);
    case 'project':
      return projectPanel(resolveProject(project), sidebar);
    case 'admin':
      return adminPanel();
    default:
      throw new Error(`unknown sidebar panel "${panel}"`);
  }
}

// Marks `activeMenuId` (item id or top-level menu id) active, and its section too, like
// Menu#serialize_for_super_sidebar does (section is_active when any child is active).
function applyActive(items, activeMenuId, activeSectionId) {
  return items.map((m) => {
    const children = (m.items || []).map((c) => ({ ...c, is_active: c.id === activeMenuId }));
    const childActive = children.some((c) => c.is_active);
    return {
      ...m,
      items: children,
      is_active: m.id === activeMenuId || m.id === activeSectionId || childActive,
    };
  });
}

// Every item id of a panel, for quick reference: node -e "import('./src/shell/sidebar_data.mjs').then(m=>console.log(m.itemIds('project')))"
export function itemIds(panel, ctx = {}) {
  const p = panelFor({ panel, group: ctx.group || 'acme-corp', project: ctx.project || 'acme-corp/checkout-service' });
  return p.items.flatMap((m) => [m.id, ...(m.items || []).map((i) => `  ${m.id} > ${i.id}  (${i.title})`)]);
}

// sidebar options (page.sidebar): { hide: [ids], pins: [ids], transform: (items) => items,
//   duoFeaturesEnabled, duoWorkflowEnabled, plan, crm, activeSectionId, extra: {...merged into data-sidebar} }
export function buildSidebarData({ user, panel, activeMenuId, group, project, sidebar = {} }) {
  const p = panelFor({ panel, group, project, sidebar });
  let items = JSON.parse(JSON.stringify(p.items));
  if (sidebar.hide?.length) {
    const hide = new Set(sidebar.hide);
    items = items
      .filter((m) => !hide.has(m.id))
      .map((m) => ({ ...m, items: (m.items || []).filter((i) => !hide.has(i.id)) }))
      .filter((m) => !(m.items.length === 0 && p.items.find((o) => o.id === m.id)?.items?.length));
  }
  if (sidebar.transform) items = sidebar.transform(items) || items;
  items = applyActive(items, activeMenuId, sidebar.activeSectionId);

  const ctxGroup = resolveGroup(group);
  const ctxProject = resolveProject(project);
  const fullPath = ctxProject?.fullPath || ctxGroup?.fullPath;
  const createNew = [];
  if (ctxProject) {
    createNew.push({
      name: 'In this project',
      items: [
        { text: 'New work item', href: `/${ctxProject.fullPath}/-/work_items/new` },
        { text: 'New merge request', href: `/${ctxProject.fullPath}/-/merge_requests/new` },
        { text: 'New branch', href: `/${ctxProject.fullPath}/-/branches/new` },
        { text: 'New snippet', href: `/${ctxProject.fullPath}/-/snippets/new` },
        { text: 'Invite team members', component: 'invite_members' },
      ],
    });
  } else if (ctxGroup) {
    createNew.push({
      name: 'In this group',
      items: [
        { text: 'New project/repository', href: `/projects/new?namespace_id=${ctxGroup.id}` },
        { text: 'New subgroup', href: `/groups/new?parent_id=${ctxGroup.id}#create-group-pane` },
        { text: 'New epic', href: `/groups/${ctxGroup.fullPath}/-/epics/new` },
        { text: 'Invite team members', component: 'invite_members' },
      ],
    });
  }
  createNew.push({
    name: createNew.length ? 'In GitLab' : 'GitLab',
    items: [
      { text: 'New project/repository', href: '/projects/new' },
      { text: 'New group', href: '/groups/new' },
      { text: 'New snippet', href: '/-/snippets/new' },
    ],
  });

  return {
    is_logged_in: true,
    is_admin: panel === 'admin',
    name: user.name,
    username: user.username,
    admin_mode: { admin_mode_feature_enabled: true, admin_mode_active: panel === 'admin', user_is_admin: panel === 'admin' },
    avatar_url: user.avatarUrl,
    logo_url: null,
    status: {
      can_update: true,
      busy: false,
      customized: false,
      availability: '',
      emoji: null,
      message_html: null,
      message: null,
      clear_after: null,
    },
    user_counts: {
      assigned_issues: 4,
      assigned_merge_requests: 2,
      review_requested_merge_requests: 1,
      todos: 0,
      last_update: Date.now(),
    },
    compare_plans_url: ctxGroup || ctxProject ? `/groups/${(ctxGroup || resolveGroup(ctxProject.namespace))?.fullPath}/-/billings` : '/pricing',
    create_new_menu_groups: createNew,
    gitlab_com_and_canary: false,
    gitlab_com_but_not_canary: true,
    canary_toggle_com_url: 'https://next.gitlab.com',
    current_context: p.currentContext,
    pinned_items: sidebar.pins || p.pins,
    is_impersonating: false,
    shortcut_links: [],
    work_items: fullPath ? { full_path: fullPath } : {},
    has_multiple_organizations: false,
    show_feature_library_feedback: false,
    show_feature_library_shimmer: false,
    ai_search_available: false,
    current_menu_items: items,
    current_context_header: p.header,
    support_path: 'https://about.gitlab.com/get-help/',
    docs_path: '/help/docs',
    display_whats_new: false,
    show_version_check: false,
    search: {
      search_path: '/search',
      issues_path: '/dashboard/issues',
      mr_path: '/dashboard/merge_requests',
      autocomplete_path: '/search/autocomplete',
      search_context: fullPath
        ? {
            ...(ctxGroup && !ctxProject ? { group: { id: ctxGroup.id, name: ctxGroup.name, full_name: ctxGroup.fullName } } : {}),
            ...(ctxProject ? { project: { id: ctxProject.id, name: ctxProject.name }, project_metadata: {} } : {}),
          }
        : {},
    },
    panel_type: panel,
    has_terms: false,
    pipeline_minutes: { show_buy_pipeline_minutes: false, show_notification_dot: false },
    merge_request_menu: [
      {
        name: 'Merge requests',
        items: [
          { text: 'Assigned', href: '/dashboard/merge_requests?assignee_username=arivera', count: 2 },
          { text: 'Review requests', href: '/dashboard/merge_requests?reviewer_username=arivera', count: 1 },
        ],
      },
    ],
    ...(sidebar.extra || {}),
  };
}

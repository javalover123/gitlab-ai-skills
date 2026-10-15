// Server-side page shell: reproduces app/views/layouts/application.html.haml + _page.html.haml +
// Layouts::StaticPanelComponent (+ layouts/group, group_settings, project, project_settings) at v19.4.1-ee
// as static HTML. Called by build/gen_pages.mjs for every page a demo's pages.mjs exports.
//
// Page definition (all optional except route + content/entry):
//   route        URL path served for this page, e.g. '/groups/acme-corp/-/settings/gitlab_duo'
//   name         output file name (default: derived from route)
//   title        array, most specific first, e.g. ['GitLab Credits dashboard']; the layout appends
//                'Settings' (settingsLayout), the group/project name and 'GitLab' like page_title does
//   panel        'group' | 'project' | 'your_work' | 'profile' | 'admin'  (default: project if project, group if group, else your_work)
//   group        key in contexts.GROUPS ('acme-corp') or a group object      (group panel / breadcrumbs / body data)
//   project      key in contexts.PROJECTS ('acme-corp/checkout-service') or a project object
//   activeMenuId sidebar item id to highlight (its section is expanded), see sidebar_data.mjs
//   sidebar      { hide, pins, transform, duoFeaturesEnabled, duoWorkflowEnabled, plan, activeSectionId, extra }
//   crumbs       extra breadcrumbs after the group/project ones: [{ text, href }]
//   breadcrumbs  full breadcrumb list (overrides the automatic group/project ones)
//   settingsLayout  true for Settings pages: adds page_bundles/settings(+projects) CSS and "Search settings"
//   searchSettings  false to drop the Search settings box on a settings page
//   bodyPage     body[data-page], e.g. 'groups:settings:gitlab_duo:show'
//   content      inner HTML of main#content-body (static HAML-equivalent markup and/or Vue mount points)
//   entry        page JS, path relative to the demo folder (default: shell boot only)
//   pageStyles   extra CSS from public/assets, e.g. ['page_bundles_settings.css']
//   fluid        true for container-fluid without container-limited
//   gon          merged into window.gon (features, licensed_features, abilities, ...)
//   user         defaults to contexts.USER
//   duoPanel     GitLab Duo AI panel (collapsed navigation rail on the right, as on GitLab.com for a user
//                with Duo) - ee/app/components/duo_chat_panel/chat_component. Default: on for group/project
//                pages (unless sidebar.duoFeaturesEnabled === false); pass false to hide it
//   saas         GitLab.com (gon.dot_com, data-is-saas); default true, false for panel 'admin' (Self-Managed)
//   headHtml     extra HTML appended to <head>
//   flash        { notice|alert|success|warning: 'message' } rendered like layouts/_flash (static; the server can
//                also set one at runtime after a form POST, see harness/serve.mjs)
import { buildSidebarData } from './sidebar_data.mjs';
import { USER, resolveGroup, resolveProject, groupChain } from './contexts.mjs';
import { flash as renderFlash } from './haml.mjs';

const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export function resolvePage(page) {
  const project = resolveProject(page.project);
  const group = resolveGroup(page.group) || (project ? resolveGroup(project.namespace) : null);
  const panel = page.panel || (project ? 'project' : group ? 'group' : 'your_work');
  return { ...page, project, group, panel, user: page.user || USER };
}

function contextCrumbs(group, project) {
  const crumbs = [];
  if (group) {
    for (const g of groupChain(group)) crumbs.push({ text: g.name, href: `/${g.fullPath}`, avatarPath: g.avatarUrl || null });
  }
  if (project) crumbs.push({ text: project.name, href: `/${project.fullPath}`, avatarPath: project.avatarUrl || null });
  return crumbs;
}

// ee/app/views/layouts/_duo_chat_panel.html.haml -> DuoChatPanel::ChatComponent#data (v19.4.1-ee)
function duoPanelHtml({ user, group, project, saas }) {
  const root = group ? groupChain(group)[0] : null;
  const data = {
    testid: 'duo-chat-panel-chat',
    'user-id': `gid://gitlab/User/${user.id || 4242}`,
    'project-id': project ? `gid://gitlab/Project/${project.id}` : '',
    'project-path': project ? project.fullPath : '',
    'namespace-id': group ? `gid://gitlab/Group/${group.id}` : '',
    'root-namespace-id': root ? `gid://gitlab/Group/${root.id}` : '',
    'resource-id': '',
    metadata: JSON.stringify({ extended_logging: false, is_team_member: false }),
    'user-model-selection-enabled': 'true',
    'agentic-available': 'true',
    'classic-available': 'false',
    'chat-disabled-reason': '',
    'credits-available': 'true',
    'default-namespace-selected': 'true',
    'agentic-unavailable-message': '',
    'duo-agent-platform-enabled': 'true',
    'force-agentic-mode-for-core-duo-users': 'false',
    'chat-title': 'GitLab Duo Agentic Chat',
    'duo-settings-path': '',
    'preferences-path': '/-/profile/preferences#user_duo_default_namespace_id',
    'explore-ai-catalog-path': '/explore/ai-catalog',
    'auto-expand': 'false',
    'trial-active': 'false',
    'subscription-active': 'true',
    'subscription-expired': 'false',
    'is-saas': String(saas),
    'is-trial': 'false',
    'can-buy-addon': 'false',
  };
  const attrs = Object.entries(data).map(([k, v]) => ` data-${k}="${esc(v)}"`).join('');
  return `<div class="ai-panels" data-testid="ai-panels"><div id="duo-chat-panel" class="duo-chat-panel"${attrs}></div></div>`;
}

export function renderPage(rawPage) {
  const page = resolvePage(rawPage);
  const {
    title = [],
    user,
    panel,
    group,
    project,
    activeMenuId,
    bodyPage = '',
    content = '',
    entry,
    pageStyles = [],
    fluid = false,
    gon = {},
    settingsLayout = false,
    searchSettings = true,
    headHtml = '',
    flash = null,
    saas = panel !== 'admin',
    duoPanel = (panel === 'group' || panel === 'project') && page.sidebar?.duoFeaturesEnabled !== false,
  } = page;

  const sidebar = buildSidebarData({ user, panel, activeMenuId, group, project, sidebar: page.sidebar });
  const breadcrumbs = page.breadcrumbs || [
    ...(panel === 'group' || panel === 'project' ? contextCrumbs(group, panel === 'project' ? project : null) : []),
    ...(page.crumbs || []),
  ];

  const styles = [...(settingsLayout ? ['page_bundles_settings.css'] : []), ...(settingsLayout && project ? ['page_bundles_projects.css'] : []), ...pageStyles];
  const fullTitle = [
    ...title,
    ...(settingsLayout ? ['Settings'] : []),
    ...(panel === 'project' && project ? [project.fullName] : []),
    ...(panel === 'group' && group ? [group.name] : []),
    'GitLab',
  ].join(' · ');

  const gonData = {
    api_version: 'v4',
    relative_url_root: '',
    gitlab_url: saas ? 'https://gitlab.com' : 'https://gitlab.acme.example',
    sprite_icons: '/assets/icons.svg',
    sprite_file_icons: '/assets/file_icons.svg',
    emoji_sprites_css_path: '',
    first_day_of_week: 0,
    ee: true,
    dot_com: saas,
    current_user_id: user.id || 4242,
    current_username: user.username,
    current_user_fullname: user.name,
    current_user_avatar_url: user.avatarUrl,
    time_display_relative: true,
    time_display_format: 0,
    subscriptions_url: 'https://customers.gitlab.com',
    ...(project ? { current_project_id: project.id } : {}),
    ...gon,
    features: { ...(gon.features || {}) },
    licensed_features: { ...(gon.licensed_features || {}) },
    abilities: { ...(gon.abilities || {}) },
  };

  // ApplicationHelper#body_data
  const body = {
    page: bodyPage,
    ...(group && panel !== 'project' ? { group: group.path, 'group-full-path': group.fullPath } : {}),
    ...(project
      ? {
          'project-id': project.id,
          project: project.path,
          'project-full-path': project.fullPath,
          group: group?.path,
          'group-full-path': group?.fullPath,
          'namespace-id': group?.id,
        }
      : {}),
  };
  const bodyAttrs = Object.entries(body)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => ` data-${k}="${esc(v)}"`)
    .join('');

  // shared/_search_settings.html.haml (rendered into :before_content by enable_search_settings)
  const searchBox =
    settingsLayout && searchSettings
      ? `<div class="gl-my-2">
<div class="js-search-settings-app">
<input class="gl-form-input form-control" type="text" placeholder="Search settings" aria-label="Search settings" disabled="disabled">
</div>
</div>`
      : '';

  return `<!DOCTYPE html>
<html class="gl-light ui-neutral with-top-bar with-header page-with-panels with-gl-container-queries user-logged-in" lang="en">
<head>
<meta charset="utf-8">
<meta content="width=device-width, initial-scale=1" name="viewport">
<title>${esc(fullTitle)}</title>
<link rel="stylesheet" href="/assets/application.css">
<link rel="stylesheet" href="/assets/tailwind.css">
<link rel="stylesheet" href="/assets/fonts.css">
${styles.map((s) => `<link rel="stylesheet" href="/assets/${s}">`).join('\n')}
<!-- Demo only: hold the first paint until the Vue shell mounts (real GitLab SSRs a sidebar placeholder); Chromium paint-holding keeps the previous page on screen meanwhile. -->
<style id="demo-boot-hide">html{visibility:hidden}</style>
<script>window.gon = ${JSON.stringify(gonData)};</script>
<script type="module" src="${entry}"></script>
${headHtml}
</head>
<body class="tab-width-8 gl-browser-chrome gl-platform-linux"${bodyAttrs}>
<div id="js-tooltips-container"></div>
<header class="super-topbar js-super-topbar"></header>
<div class="layout-page js-page-layout page-with-super-sidebar">
  <aside class="js-super-sidebar super-sidebar super-sidebar-loading" data-sidebar="${esc(JSON.stringify(sidebar))}" data-command-palette="${esc('{}')}" data-is-saas="${saas ? 'true' : 'false'}"></aside>
  <div class="broadcast-wrapper gl-rounded-lg gl-overflow-hidden"></div>
  <div class="panels-container gl-flex gl-gap-3">
    <div class="content-panels gl-flex-1 gl-w-full gl-flex gl-gap-0 gl-relative js-content-panels gl-@container/content-panels">
      <div class="paneled-view static-panel js-static-panel js-paneled-view content-wrapper">
        <div class="panel-header">
          <div class="panel-header-inner js-panel-header-inner">
            <div id="js-vue-page-breadcrumbs-wrapper" data-testid="breadcrumb-links">
              <div id="js-vue-page-breadcrumbs" data-breadcrumbs-json="${esc(JSON.stringify(breadcrumbs))}"></div>
              <div id="js-injected-page-breadcrumbs"></div>
            </div>
            <div id="js-page-breadcrumbs-extra"></div>
            <div class="panel-header-inner-actions">
              <div class="panel-header-inner-actions-portal-target js-panel-actions-portal-target"></div>
            </div>
          </div>
        </div>
        <div class="panel-content">
          <div class="panel-content-inner js-static-panel-inner">
            <div class="container-fluid${fluid ? '' : ' container-limited'}">
              <main class="content gl-@container/panel" id="content-body" itemscope itemtype="http://schema.org/SoftwareSourceCode">
                <div id="js-drawer-container"></div>
                <div class="flash-container flash-container-page sticky" data-testid="flash-container">${flash ? renderFlash(flash) : ''}<div id="js-global-alerts"></div></div>
${searchBox}
${content}
              </main>
            </div>
          </div>
        </div>
      </div>
      <div id="contextual-panel-portal" class="paneled-view-portal gl-@container/panel !gl-absolute gl-rounded-l-xl gl-shadow-lg gl-bg-default @xl/content-panels:gl-w-1/2 @xl/content-panels:gl-rounded-l-none @xl/content-panels:gl-shadow-none @xl/content-panels:!gl-relative @xl/content-panels:gl-bg-transparent gl-right-0"></div>
    </div>
  </div>
${duoPanel ? duoPanelHtml({ user, group, project, saas }) : ''}
</div>
</body>
</html>
`;
}

// Page bootstrap shared by every demo page. Mirrors the parts of GitLab's
// `~/commons` + `entrypoints/super_sidebar.js` that matter for rendering.
// Every entry file must `import '@demo/src/shell/boot';` FIRST.
import '~/commons/vue';
import '~/commons/gitlab_ui';
import '~/behaviors/configure_path_helpers';
import {
  initSuperSidebar,
  initPageBreadcrumbs,
  getSuperSidebarData,
  initSuperTopbar,
} from '~/super_sidebar/super_sidebar_bundle';
import initSettingsPanels from '~/settings_panels';
import initSearchSettings from '~/search_settings';
import { installMockBackend, mockBackend } from './mock_backend';

export { mockBackend };
export { createMockApolloClient, MockGraphQLError } from './mock_apollo';

installMockBackend();

// Async sidebar pill counts (super_sidebar.query.graphql). Override per page with
// mockBackend.graphql({ getAsyncSuperSidebarData: ... }) or window.__demoSidebarCounts before first paint.
mockBackend.graphql({
  getAsyncSuperSidebarData: ({ fullPath }) => {
    const isProject = document.body.dataset.projectFullPath === fullPath;
    const counts = {
      openIssuesCount: isProject ? 38 : 214,
      openMergeRequestsCount: isProject ? 12 : 47,
      openEpicsCount: isProject ? null : 18,
      openWorkItemsCount: isProject ? 41 : 232,
      ...(window.__demoSidebarCounts || {}),
    };
    return {
      namespace: {
        __typename: 'Namespace',
        id: `gid://gitlab/Namespaces/${isProject ? 'ProjectNamespace' : 'GroupNamespace'}/${fullPath}`,
        sidebar: { __typename: 'NamespaceSidebar', ...counts },
      },
    };
  },
});

const superSidebarData = getSuperSidebarData();
initSuperSidebar(superSidebarData);
initSuperTopbar(superSidebarData);
initPageBreadcrumbs();
document.body.classList.add('page-initialised');

// Settings pages (HAML `section.settings` blocks + "Search settings"), as pages/*/edit/index.js do.
if (document.querySelector('section.settings')) initSettingsPanels();
if (document.querySelector('.js-search-settings-app')) initSearchSettings();

// Runtime flash set by harness/serve.mjs after a mocked form POST (cookie demo_flash = JSON {notice: '...'}).
const FLASH_VARIANT = { alert: 'danger', notice: 'info', success: 'success', warning: 'warning' };
const FLASH_ICON = { danger: 'error', info: 'information-o', success: 'check-circle', warning: 'warning' };
try {
  const m = document.cookie.match(/(?:^|;\s*)demo_flash=([^;]+)/);
  if (m) {
    document.cookie = 'demo_flash=; Max-Age=0; path=/';
    const entries = JSON.parse(decodeURIComponent(m[1]));
    const container = document.querySelector('.flash-container');
    Object.entries(entries).forEach(([key, message]) => {
      const variant = FLASH_VARIANT[key] || 'info';
      const div = document.createElement('div');
      div.className = `gl-alert gl-alert-${variant} flash-${key}`;
      div.setAttribute('role', 'alert');
      div.dataset.testid = `alert-${variant}`;
      div.innerHTML = `<div class="gl-alert-icon-container"><svg class="s16 gl-alert-icon gl-alert-icon-no-title" data-testid="${FLASH_ICON[variant]}-icon"><use href="/assets/icons.svg#${FLASH_ICON[variant]}"></use></svg></div><button class="gl-button btn btn-icon btn-sm btn-default btn-default-tertiary js-close gl-dismiss-btn" aria-label="Dismiss" type="button"><svg class="s16 gl-icon gl-button-icon" data-testid="close-icon"><use href="/assets/icons.svg#close"></use></svg></button><div class="gl-alert-content" role="alert"><div class="gl-alert-body"></div></div>`;
      div.querySelector('.gl-alert-body').textContent = message;
      container?.insertBefore(div, container.querySelector('#js-global-alerts'));
    });
  }
} catch (e) {
  /* ignore */
}
document.addEventListener('click', (e) => {
  const close = e.target.closest('.flash-container .js-close');
  if (close) close.closest('.gl-alert')?.remove();
});

// Static (HAML-style) forms marked data-demo-persist keep their field values across the mocked
// POST -> redirect round trip (sessionStorage), so a saved checkbox stays checked after "Save changes".
export const demoState = {
  get(key, fallback = null) {
    try {
      const v = sessionStorage.getItem(`__demoState:${key}`);
      return v === null ? fallback : JSON.parse(v);
    } catch (e) {
      return fallback;
    }
  },
  set(key, value) {
    try {
      sessionStorage.setItem(`__demoState:${key}`, JSON.stringify(value));
    } catch (e) {
      /* ignore */
    }
  },
};
document.querySelectorAll('form[data-demo-persist]').forEach((f) => {
  const key = `form:${f.getAttribute('action')}:${f.id || ''}`;
  const saved = demoState.get(key);
  if (saved) {
    f.querySelectorAll('input[name], select[name], textarea[name]').forEach((el) => {
      if (!(el.name in saved) || el.type === 'hidden') return;
      if (el.type === 'checkbox' || el.type === 'radio') el.checked = saved[el.name].includes(el.value);
      else [el.value] = saved[el.name];
    });
  }
  f.addEventListener('submit', () => {
    const values = {};
    f.querySelectorAll('input[name], select[name], textarea[name]').forEach((el) => {
      if (el.type === 'hidden') return;
      values[el.name] = values[el.name] || [];
      if ((el.type === 'checkbox' || el.type === 'radio') && !el.checked) return;
      values[el.name].push(el.value);
    });
    demoState.set(key, { ...(demoState.get(key) || {}), ...values });
  });
});

// GitLab Duo AI panel (layout option duoPanel: true) - entrypoints/duo_panel.js
// Default answers for what the collapsed panel queries on load; demos that open the chat add more
// handlers with mockBackend.graphql({...}) (see console "[mock-backend] graphql passthrough X").
if (document.getElementById('duo-chat-panel')) {
  const agent = (id, name, description, reference) => ({
    __typename: 'AiFoundationalChatAgent',
    id: `gid://gitlab/Ai::FoundationalChatAgent/${id}`,
    name,
    description,
    reference,
    referenceWithVersion: `${reference}/v1`,
    version: 'v1',
    avatarUrl: null,
    selectableInChat: true,
    tools: [],
    flowConfig: null,
  });
  mockBackend.graphql({
    getFoundationalChatAgents: () => ({
      aiFoundationalChatAgents: {
        __typename: 'AiFoundationalChatAgentConnection',
        nodes: [
          agent(1, 'GitLab Duo', 'General-purpose agent for your software development lifecycle.', 'chat'),
          agent(2, 'Planner', 'Helps plan and break down work items.', 'duo_planner'),
          agent(3, 'Security Analyst', 'Triages and explains vulnerabilities.', 'security_analyst_agent'),
        ],
      },
    }),
    getConfiguredAgents: () => ({
      aiCatalogConfiguredItems: {
        __typename: 'AiCatalogItemConsumerConnection',
        nodes: [],
        pageInfo: { __typename: 'PageInfo', hasNextPage: false, endCursor: null },
      },
    }),
  });
  import('ee/ai/init_duo_panel').then(({ initDuoPanel }) => initDuoPanel());
}

// Reveal the page once the page-specific app (imported after this module) has mounted too.
setTimeout(() => requestAnimationFrame(() => document.getElementById('demo-boot-hide')?.remove()), 0);

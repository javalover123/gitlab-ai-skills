// Pages for the "personal GitLab Credits usage" demo (GitLab 19.4).
import fs from 'node:fs';
import { GROUPS } from './data.js';

import { USER } from '../../src/shell/contexts.mjs';

const entry = (f) => f; // entries are relative to this demo folder

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');

export default [
  {
    name: 'home',
    route: '/',
    title: ['Home'],
    user: USER,
    panel: 'your_work',
    activeMenuId: 'homepage_menu',
    breadcrumbs: [{ text: 'Your work', href: '/' }, { text: 'Home', href: '/' }],
    bodyPage: 'root:index',
    entry: entry('entry_home.js'),
    pageStyles: ['page_bundles_personal_homepage.css'],
    content: `<div id="js-homepage-app"></div>`,
  },
  {
    name: 'profile',
    route: '/-/user_settings/profile',
    title: ['Edit Profile', 'User Settings'],
    user: USER,
    panel: 'profile',
    activeMenuId: 'profile_menu',
    breadcrumbs: [
      { text: 'User Settings', href: '/-/user_settings/profile' },
      { text: 'Edit Profile', href: '/-/user_settings/profile' },
    ],
    bodyPage: 'user_settings:profiles:show',
    entry: entry('entry_profile.js'),
    pageStyles: ['page_bundles_profile.css'],
    content: fs.readFileSync(new URL('./profile_content.html', import.meta.url), 'utf8'),
  },
  {
    // ee/app/views/profiles/gitlab_credits_dashboard/index.html.haml
    name: 'credits',
    route: '/-/profile/gitlab_credits_dashboard',
    title: ['Your GitLab Credits usage', 'User Settings'],
    user: USER,
    panel: 'profile',
    activeMenuId: 'gitlab_credits_dashboard_menu',
    breadcrumbs: [
      { text: 'User Settings', href: '/-/user_settings/profile' },
      { text: 'Your GitLab Credits usage', href: '/-/profile/gitlab_credits_dashboard' },
    ],
    bodyPage: 'profiles:gitlab_credits_dashboard:index',
    entry: entry('entry_credits.js'),
    content: `<h1 class="gl-mb-3">Your GitLab Credits usage</h1>
<div id="js-user-gitlab-credits-dashboard" data-groups-with-gitlab-credits="${esc(JSON.stringify(GROUPS))}"></div>`,
  },
];

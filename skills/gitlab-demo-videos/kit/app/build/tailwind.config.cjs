// GitLab's own Tailwind config (gl-src/config/tailwind.config.js) with content paths
// pointed at the demo shell/scenarios plus the GitLab sources we render.
const path = require('path');
const base = require('../../gl-src/config/tailwind.config.js');
const root = path.resolve(__dirname, '../../gl-src');
const app = path.resolve(__dirname, '..');
module.exports = {
  ...base,
  content: [
    `${app}/src/**/*.{vue,js,html}`,
    `${app}/demos/**/*.{js,mjs,html,vue}`,
    `${app}/src/**/*.mjs`,
    `${root}/{ee/,}app/assets/javascripts/**/*.{vue,js}`,
    `!${root}/app/assets/javascripts/locale/`,
    `${root}/{ee/,}app/helpers/**/*.rb`,
    `${root}/{ee/,}app/components/**/*.{haml,rb}`,
    `${root}/{ee/,}app/views/**/*.haml`,
    `${app}/node_modules/@gitlab/ui/src/**/*.{vue,js}`,
  ],
};

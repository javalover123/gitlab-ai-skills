// Node-side helpers that emit the exact markup of GitLab's server-rendered (HAML / ViewComponent)
// building blocks at v19.4.1-ee, for hand-built static pages. Use them in pages.mjs `content`.
//
//   import { settingsBlock, button, checkbox, pageHeading, sprite, esc } from '../../src/shell/haml.mjs';
//
// Sources: app/components/layouts/{settings_block,page_heading,crud}_component.html.haml,
// app/components/pajamas/{button,checkbox,animated_icon}_component.*, app/helpers/icons_helper.rb#sprite_icon.
// JS behaviour (expand/collapse of `section.settings`, "Search settings") is wired by shell/boot.js.

export const esc = (s) =>
  String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const attrs = (o = {}) =>
  Object.entries(o)
    .filter(([, v]) => v !== undefined && v !== null && v !== false)
    .map(([k, v]) => (v === true ? ` ${k}` : ` ${k}="${esc(v)}"`))
    .join('');

// IconsHelper#sprite_icon
export function sprite(icon, { size = 16, cls = '', variant, ariaLabel } = {}) {
  const VARIANT = { subtle: 'gl-fill-icon-subtle', strong: 'gl-fill-icon-strong', success: 'gl-fill-icon-success', danger: 'gl-fill-icon-danger', warning: 'gl-fill-icon-warning', info: 'gl-fill-icon-info', disabled: 'gl-fill-icon-disabled', default: 'gl-fill-icon-default', link: 'gl-fill-icon-link' };
  const c = [size ? `s${size}` : null, variant ? VARIANT[variant] : null, cls || null].filter(Boolean).join(' ');
  return `<svg${attrs({ class: c || undefined, 'data-testid': `${icon}-icon`, 'aria-label': ariaLabel })}><use href="/assets/icons.svg#${icon}"></use></svg>`;
}

// Pajamas::ButtonComponent
export function button({
  text = '',
  category = 'primary',
  variant = 'default',
  size = 'medium',
  type = 'button',
  icon,
  href,
  disabled = false,
  loading = false,
  cls = '',
  attrs: extra = {},
} = {}) {
  const VAR = { default: 'btn-default', confirm: 'btn-confirm', danger: 'btn-danger', link: 'btn-link', reset: 'btn-gl-reset' };
  const classes = ['gl-button btn'];
  if (disabled || loading) classes.push('disabled');
  if (icon && !text) classes.push('btn-icon');
  classes.push(size === 'small' ? 'btn-sm' : 'btn-md', VAR[variant]);
  if (!['link', 'reset'].includes(variant) && category !== 'primary') classes.push(`${VAR[variant]}-${category}`);
  if (cls) classes.push(cls);
  const inner = [
    loading ? '<span class="gl-spinner-container gl-button-icon gl-button-loading-indicator" role="status"><span aria-label="Loading" class="gl-spinner gl-spinner-sm gl-spinner-dark !gl-align-text-bottom"></span></span>' : '',
    icon && !loading ? sprite(icon, { cls: 'gl-icon gl-button-icon' }) : '',
    text ? `<span class="gl-button-text">${text}</span>` : '',
  ].join('');
  const a = { ...extra, class: classes.join(' ') };
  if (href) return `<a href="${esc(href)}"${attrs(a)}>${inner}</a>`;
  return `<button${attrs({ ...a, type, disabled: disabled || loading ? 'disabled' : undefined, 'aria-disabled': disabled || loading ? 'true' : undefined })}>${inner}</button>`;
}

// Pajamas::AnimatedIconComponent (chevron_lg_right_down only - what settings blocks use)
const chevron = (on) =>
  `<svg class="gl-animated-icon gl-animated-icon-current ${on ? 'gl-animated-icon-on' : 'gl-animated-icon-off'} js-settings-icon" role="presentation" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path class="gl-animated-chevron-lg-right-down-arrow" d="M5.75 13.2537L11.0018 8.00183L5.75 2.75" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg>`;

// Layouts::SettingsBlockComponent - a collapsible `section.settings` block (Expand / Collapse).
export function settingsBlock({ heading, description = '', id, testid, expanded = false, body = '', cls = '' }) {
  const label = `${expanded ? 'Collapse' : 'Expand'} ${heading}`;
  const desc = description
    ? /^\s*</.test(description)
      ? `<div class="gl-text-subtle gl-m-0">${description}</div>`
      : `<p class="gl-text-subtle gl-m-0">${description}</p>`
    : '';
  return `<section${attrs({ class: ['settings no-animate', expanded ? 'expanded' : '', cls].filter(Boolean).join(' '), id, 'data-testid': testid })}>
<div class="gl-flex gl-justify-between gl-items-start gl-gap-x-3 gl-pt-5">
<div class="gl-shrink-0 gl-px-2 gl-py-0 -gl-mr-3 @sm/panel:gl-p-2 @sm/panel:gl-mr-0">
<button class="gl-button btn btn-sm btn-default btn-default-tertiary btn-icon settings-toggle js-settings-toggle" aria-label="${esc(label)}" type="button"><div class="gl-sr-only">${expanded ? 'Collapse' : 'Expand'}</div>
${chevron(expanded)}</button>
</div>
<div class="gl-grow">
<h2 class="gl-heading-2 gl-cursor-pointer !gl-mb-2 js-settings-toggle js-settings-toggle-trigger-only" data-settings-block-title="">${heading}</h2>
${desc}
</div>
</div>
<div class="settings-content">
<div class="gl-pl-7 gl-mt-5 @sm/panel:gl-pl-8">
${body}
</div>
</div>
</section>`;
}

// Layouts::PageHeadingComponent
export function pageHeading({ heading, description = '', actions = '' }) {
  return `<header class="gl-flex gl-flex-wrap gl-items-center gl-justify-between gl-gap-y-3 gl-mt-2 gl-mb-5">
<div class="gl-flex gl-flex-wrap gl-justify-between gl-gap-x-5 gl-gap-y-3 gl-w-full @md/panel:gl-flex-nowrap">
<h1 class="gl-heading-1 !gl-m-0" data-testid="page-heading">${heading}</h1>
${actions ? `<div class="page-heading-actions gl-self-start gl-flex gl-flex-wrap gl-items-center gl-gap-3 gl-w-full gl-shrink-0 @sm/panel:gl-w-auto @md/panel:gl-mt-1 @lg/panel:gl-mt-2" data-testid="page-heading-actions">${actions}</div>` : ''}
</div>
${description ? `<div class="gl-w-full gl-text-subtle" data-testid="page-heading-description">${description}</div>` : ''}
</header>`;
}

// Pajamas::CheckboxComponent via gitlab_ui_form_for (form.gitlab_ui_checkbox_component)
// name: e.g. 'group[display_gitlab_credits_user_data]'
export function checkbox({ name, id, label, helpText = '', checked = false, disabled = false, wrapperCls = '', inputAttrs = {} }) {
  const inputId = id || name.replace(/\]\[|\[|\]/g, '_').replace(/_$/, '');
  return `<div class="gl-form-checkbox custom-control custom-checkbox${wrapperCls ? ` ${wrapperCls}` : ''}">
<input name="${esc(name)}" type="hidden" value="0" autocomplete="off"><input${attrs({ class: 'custom-control-input', type: 'checkbox', value: '1', checked, disabled, name, id: inputId, ...inputAttrs })}>
<label class="custom-control-label" for="${esc(inputId)}"><span>${label}</span>${helpText ? `<p class="help-text" data-testid="pajamas-component-help-text">${helpText}</p>` : ''}</label>
</div>`;
}

// Standard settings form footer (f.submit _('Save changes'), pajamas_button confirm)
export const saveButton = (text = 'Save changes', extra = {}) =>
  button({ text, variant: 'confirm', type: 'submit', attrs: { 'data-testid': 'save-changes-button', ...extra } });

// Help link as rendered by link_to(..., help_page_path(...), target: '_blank')
export const helpLink = (text, href = '/help') => `<a target="_blank" rel="noopener noreferrer" href="${esc(href)}">${text}</a>`;

// Pajamas::AlertComponent (as layouts/_flash renders it for flash[:notice|:alert|:success|:warning])
const ALERT_ICONS = { info: 'information-o', warning: 'warning', success: 'check-circle', danger: 'error', tip: 'bulb' };
export function alert({ variant = 'info', title = '', body = '', dismissible = true, actions = '', cls = '', testid } = {}) {
  const classes = [`gl-alert-${variant}`];
  if (!dismissible) classes.push('gl-alert-not-dismissible');
  if (title) classes.push('gl-alert-has-title');
  return `<div class="gl-alert ${classes.join(' ')}${cls ? ` ${cls}` : ''}" role="alert"${testid ? ` data-testid="${esc(testid)}"` : ''}>
<div class="gl-alert-icon-container">${sprite(ALERT_ICONS[variant], { cls: `gl-alert-icon${title ? '' : ' gl-alert-icon-no-title'}` })}</div>
${dismissible ? button({ category: 'tertiary', icon: 'close', size: 'small', cls: 'js-close gl-dismiss-btn', attrs: { 'aria-label': 'Dismiss' } }) : ''}
<div class="gl-alert-content" role="alert">
${title ? `<h2 class="gl-alert-title">${title}</h2>` : ''}
${body ? `<div class="gl-alert-body">${body}</div>` : ''}
${actions ? `<div class="gl-alert-actions">${actions}</div>` : ''}
</div>
</div>`;
}

// layouts/_flash: flash = { notice: 'Group was successfully updated.' } (keys: notice|alert|success|warning)
const FLASH_VARIANT = { alert: 'danger', notice: 'info', success: 'success', warning: 'warning' };
export function flash(entries = {}) {
  return Object.entries(entries)
    .map(([key, value]) =>
      alert({ variant: FLASH_VARIANT[key] || 'info', body: esc(value), dismissible: ['alert', 'notice', 'success'].includes(key), cls: `flash-${key}`, testid: `alert-${FLASH_VARIANT[key] || 'info'}` }),
    )
    .join('\n');
}

// Layouts::SettingsSectionComponent - a non-collapsible settings section with sticky header
// (used e.g. by projects/settings/merge_requests sections such as "GitLab Duo Code Review").
export function settingsSection({ heading, description = '', id, testid, cls = '', body = '' }) {
  return `<section${attrs({ class: ['settings-section js-search-settings-section', cls].filter(Boolean).join(' '), id, 'data-testid': testid })}>
<div class="settings-sticky-header${description ? '' : ' gl-mb-4'}">
<h2 class="gl-heading-2 gl-mb-0">${heading}</h2>
</div>
${description ? `<div class="settings-sticky-header-description gl-mb-6"><p class="gl-text-subtle gl-mb-0">${description}</p></div>` : ''}
<div class="gl-mt-3" data-testid="settings-section-body">
${body}
</div>
</section>`;
}

// Rails form wrapper as gitlab_ui_form_for renders it (hidden _method + authenticity token).
// method: 'patch' | 'put' | 'post'. The mocked server answers it via app/demos/<slug>/rest.mjs
// (typically { redirect, flash }). persist (default true): field values survive the redirect (shell/boot.js).
export function form({ action, method = 'patch', cls = '', body = '', id, persist = true }) {
  return `<form${attrs({ class: cls || undefined, id, action, 'accept-charset': 'UTF-8', method: 'post', 'data-demo-persist': persist })}><input type="hidden" name="_method" value="${esc(method)}" autocomplete="off"><input type="hidden" name="authenticity_token" value="demo-token" autocomplete="off">
${body}
</form>`;
}

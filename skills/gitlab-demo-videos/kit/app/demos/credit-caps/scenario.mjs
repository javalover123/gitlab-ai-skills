// "Set credit caps and unblock a user" (written against GitLab 19.4; GitLab.com, group Owner).
// Run with: node harness/narrated.mjs credit-caps   (narration-paced; silent only: node harness/record.mjs credit-caps)
// say(<id>) starts line <id> of narration/scripts/credit-caps.json; settle() waits until it has been spoken.
import { GITLAB_VERSION } from '../../src/shell/gitlab_version.mjs';

const DASH = '/groups/acme-corp/-/settings/gitlab_credits_dashboard';

export const meta = {
  title: `Set credit caps and unblock a user (GitLab ${GITLAB_VERSION})`,
  startRoute: DASH,
  demoTime: '2026-09-25T10:20:00-04:00',
  timezoneId: 'America/New_York',
  cursorStart: { x: 1480, y: 240 },
};

// Eased scroll of the element's scroll container so `locator` ends up `top` px from the viewport top.
async function smoothScrollTo(page, locator, { top = 120, duration = 1000 } = {}) {
  const handle = await locator.elementHandle();
  await page.evaluate(
    async ([el, topPx, ms]) => {
      let sc = el.parentElement;
      while (sc && !(sc.scrollHeight > sc.clientHeight + 4 && /auto|scroll/.test(getComputedStyle(sc).overflowY))) {
        sc = sc.parentElement;
      }
      sc = sc || document.scrollingElement;
      const start = sc.scrollTop;
      const target = Math.max(0, Math.min(sc.scrollHeight - sc.clientHeight, start + el.getBoundingClientRect().top - topPx));
      const t0 = performance.now();
      await new Promise((resolve) => {
        const step = (now) => {
          const p = Math.min(1, (now - t0) / ms);
          const e = p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
          sc.scrollTop = start + (target - start) * e;
          if (p < 1) requestAnimationFrame(step);
          else resolve();
        };
        requestAnimationFrame(step);
      });
    },
    [handle, top, duration],
  );
}

export default async function run({ page, cursor, pause, mark, caption, waitForIdle, type, say, settle }) {
  const usersTab = () => page.getByRole('tab', { name: 'Usage by user' });
  const statusBadge = (name) =>
    page.locator('tr', { hasText: name }).locator('[data-testid="usage-control-status-cell"] .gl-badge');
  const toast = (text) => page.locator('.gl-toast', { hasText: text });
  const capsButton = () => page.getByRole('link', { name: 'Credit caps' });
  const toDashboard = async () => {
    await cursor.click(page.getByRole('link', { name: 'GitLab Credits dashboard', exact: true }).first(), { dx: 0.4 });
    await page.waitForURL((u) => u.pathname === DASH);
    await usersTab().waitFor();
    await statusBadge('Priya Natarajan').waitFor();
    await cursor.sync();
  };

  // 1. The group's GitLab Credits dashboard -> Credit caps.
  await caption('Settings > GitLab Credits', { step: 'Step 1' });
  await pause(400);
  say('intro');
  await pause(2200);
  mark('dashboard');
  await cursor.moveTo(capsButton(), { duration: 1400 });
  await settle(0);
  await cursor.click(capsButton());
  await page.waitForURL('**/credit_caps');
  await page.getByText('Per-user cap overrides require flat cap value').waitFor();
  await cursor.sync();
  await pause(300);

  // 2. Flat per-user cap: 400 credits, enforced.
  await caption('Set a flat per-user cap', { step: 'Step 2' });
  say('flatCap');
  await pause(1200);
  const capInput = page.locator('#flat-user-cap-input');
  await cursor.click(capInput, { dx: 0.3 });
  await type(capInput, '400', { delay: 120 });
  await pause(900);
  await cursor.click(page.locator('[data-testid="cap-enabled-toggle"] button'));
  await settle(700);

  await caption("Per user, per month. Counts only after a user's included credits run out.", { step: 'Step 2' });
  say('flatCapRules');
  await pause(1800);
  await cursor.moveTo(page.locator('[data-testid="save-button"]'), { duration: 1200 });
  await settle(0);
  await cursor.click(page.locator('[data-testid="save-button"]'));
  await toast('Flat cap saved.').waitFor();
  await page.getByText('No per-user overrides set.').waitFor();
  mark('flat-cap-saved');
  await pause(700);

  // 3. Dashboard: a heavy user is now blocked.
  await caption('Usage control status shows who reached the cap', { step: 'Step 3' });
  say('backToDash');
  await toDashboard();
  await pause(200);
  await smoothScrollTo(page, usersTab(), { top: 150, duration: 1100 });
  await settle(200);
  say('blocked');
  await cursor.moveTo(statusBadge('Priya Natarajan'), { duration: 900 });
  mark('blocked');
  await settle(800);

  // 4. Raise one user's cap with an override.
  await caption("Raise one user's cap with an override", { step: 'Step 4' });
  say('openOverride');
  await smoothScrollTo(page, page.locator('h1').first(), { top: 90, duration: 900 });
  await pause(200);
  await cursor.click(capsButton());
  await page.waitForURL('**/credit_caps');
  await page.getByText('No per-user overrides set.').waitFor();
  await cursor.sync();
  await pause(300);
  await cursor.click(page.locator('[data-testid="user-credit-caps-add-override-button"]'));
  const modal = page.locator('[data-testid="add-user-cap-override-modal"]');
  await modal.locator('#user-override-select').waitFor();
  await settle(600);

  say('overrideModal');
  const search = modal.locator('#user-override-select');
  await cursor.click(search, { dx: 0.3 });
  await type(search, 'priya', { delay: 100 });
  const option = page.locator('.gl-token-selector-dropdown, .dropdown-menu').getByText('Priya Natarajan').first();
  await option.waitFor();
  await pause(450);
  await cursor.click(option, { dx: 0.3 });
  const overrideCap = modal.locator('#add-cap-override-cap-input');
  await cursor.click(overrideCap, { dx: 0.5 });
  await overrideCap.selectText();
  await type(overrideCap, '600', { delay: 120 });
  await pause(700);
  mark('override-modal');
  await cursor.click(modal.locator('[data-testid="add-cap-override-submit-button"]'));
  await toast('Override saved.').waitFor();
  await page.locator('[data-testid="user-credit-caps-overrides-table"]').getByText('Priya Natarajan').waitFor();
  mark('override-saved');
  await settle(700);

  // 5. Back on the dashboard: unblocked.
  await caption('Override applies: back to Regular usage', { step: 'Step 5' });
  say('checkAgain');
  await toDashboard();
  await pause(200);
  await smoothScrollTo(page, usersTab(), { top: 150, duration: 1100 });
  await settle(200);
  say('unblocked');
  await cursor.moveTo(statusBadge('Priya Natarajan'), { duration: 900 });
  mark('unblocked');
  await settle(1000);

  // End card (lower third).
  await caption('Caps use recent usage data. Hard stop: turn off GitLab Duo.');
  say('hardStop');
  await cursor.moveToPoint(1500, 620, { duration: 900 });
  await settle(1000);
  await caption(`GitLab ${GITLAB_VERSION} on GitLab.com  ·  Self-Managed: Admin > GitLab Credits > Credit caps  ·  Dedicated: GraphQL API`);
  say('outro');
  await pause(600);
  mark('end');
  await settle(2200);
}

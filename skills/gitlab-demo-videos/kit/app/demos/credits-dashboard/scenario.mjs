// Scenario: a developer checks their own GitLab Credits usage (written against GitLab 19.4).
// Run with: node harness/narrated.mjs credits-dashboard   (narration-paced; silent only: node harness/record.mjs credits-dashboard)
// say(<id>) starts the line <id> of narration/scripts/credits-dashboard.json; settle() waits until it has been spoken.
import { GITLAB_VERSION } from '../../src/shell/gitlab_version.mjs';

export const meta = {
  title: `Your GitLab Credits usage (GitLab ${GITLAB_VERSION})`,
  startRoute: '/',
  // Wall-clock the demo pretends it is (America/New_York).
  demoTime: '2026-09-25T15:40:00-04:00',
  timezoneId: 'America/New_York',
  cursorStart: { x: 1480, y: 700 },
};

// Finds the rendered columns of the credits chart (ECharts SVG renderer) left-to-right.
async function chartBars(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('svg path')]
      .filter((p) => p.getAttribute('fill') === 'rgb(97,122,226)')
      .map((p) => p.getBoundingClientRect())
      .filter((r) => r.width > 4 && r.width < 80 && r.height > 1)
      .map((r) => ({ x: r.x + r.width / 2, top: r.y, bottom: r.y + r.height, h: r.height }))
      .sort((a, b) => a.x - b.x),
  );
}

export default async function run({ page, cursor, pause, mark, waitForIdle, say, settle }) {
  const listboxOption = (name) => page.getByRole('option', { name, exact: true });
  const toggle = (text) => page.locator('button.gl-new-dropdown-toggle', { hasText: text }).first();

  // 1. Start on the personal homepage.
  await waitForIdle();
  await pause(300);
  mark('home');
  await say('intro');
  await settle(400);

  // 2. Avatar menu -> Edit profile.
  say('navigate');
  await cursor.click(page.locator('[data-testid="user-menu-toggle"]').first());
  await pause(900);
  await cursor.click(page.locator('[data-testid="edit-profile-item"]'), { dx: 0.25 });
  await page.waitForURL('**/-/user_settings/profile');
  await waitForIdle();
  await cursor.sync();
  await pause(500);

  // 3. User settings sidebar -> GitLab Credits.
  await cursor.click(page.locator('#super-sidebar').getByRole('link', { name: 'GitLab Credits' }), { dx: 0.3 });
  await page.waitForURL('**/-/profile/gitlab_credits_dashboard');
  await cursor.sync();
  await page.getByText('Credits used in this billing period').waitFor();
  await page.locator('[data-testid="range-total-usage-card"]').waitFor();
  await settle(900);
  mark('dashboard');
  // Glide over the headline numbers so the viewer reads them.
  say('totals');
  await cursor.moveTo(page.locator('[data-testid="billing-period-credits"]'), { dx: 0.9, duration: 900 });
  await pause(900);
  await cursor.moveTo(page.locator('[data-testid="peak-day-usage-card"]'), { dx: 0.45, dy: 0.62, duration: 1000 });
  await settle(1000);

  // 4. Date range: Last 7 days, then back to This month.
  say('range');
  await cursor.click(toggle('This month'));
  await pause(800);
  await cursor.click(listboxOption('Last 7 days'), { dx: 0.3 });
  await page.locator('[data-testid="range-total-usage-card"]').waitFor();
  await pause(2300);
  mark('last7');
  await cursor.click(toggle('Last 7 days'));
  await pause(700);
  await cursor.click(listboxOption('This month'), { dx: 0.3 });
  await page.locator('[data-testid="range-total-usage-card"]').waitFor();
  await settle(1200);

  // 5. Products filter: only Agentic Chat.
  say('products');
  await cursor.click(toggle('Select products'));
  await pause(900);
  await cursor.click(listboxOption('Agentic Chat'), { dx: 0.35 });
  await pause(700);
  // Clicking away closes the listbox; the filter applies on blur (products_dropdown_filter.vue).
  const empty = await cursor.point(page.locator('h1'), { dx: 1, ox: 260 });
  await cursor.clickPoint(empty.x, empty.y);
  await page.locator('[data-testid="range-total-usage-card"]').waitFor();
  await pause(1200);
  mark('filtered');
  await settle(400);

  // 6. Hover the peak day column to show the chart tooltip.
  let bars = await chartBars(page);
  say('tooltip');
  const peak = bars.reduce((a, b) => (b.h > a.h ? b : a), bars[0]);
  await cursor.moveToPoint(peak.x, peak.top + Math.min(40, peak.h / 2), { duration: 1000 });
  await pause(1900);
  mark('tooltip');
  const later = bars.filter((b) => b.x > peak.x + 100).reduce((a, b) => (b.h > a.h ? b : a), bars[bars.length - 1]);
  await cursor.moveToPoint(later.x, later.top + Math.min(30, later.h / 2), { duration: 700 });
  await settle(700);
  // Move off the chart so the tooltip hides.
  await cursor.moveToPoint(1500, 520, { duration: 600 });
  await pause(200);

  // 7. Remove the product filter first: switching group remounts the filters (the dashboard
  // skeleton replaces them), which resets the dropdown's label but not the applied filter
  // (upstream 19.4 behaviour) - deselecting avoids a confusing "Select products" + filtered chart.
  await cursor.click(toggle('1 selected'));
  await pause(600);
  await cursor.click(listboxOption('Agentic Chat'), { dx: 0.35 }); // deselect
  await pause(300);
  const away = await cursor.point(page.locator('h1'), { dx: 1, ox: 260 });
  await cursor.clickPoint(away.x, away.y);
  await page.locator('[data-testid="range-total-usage-card"]').waitFor();
  await pause(500);

  // 8. Switch group.
  say('groups');
  await cursor.click(page.locator('[data-testid="group-selector"] button').first());
  await pause(900);
  await cursor.click(listboxOption('Acme Labs'), { dx: 0.3 });
  await page.getByText('Track your GitLab Credits consumption for').waitFor();
  await page.locator('[data-testid="range-total-usage-card"]').waitFor();
  await pause(900);
  await settle(600);
  say('outro');
  await cursor.moveToPoint(1450, 470, { duration: 900 });
  await settle(400);
  mark('end');
}

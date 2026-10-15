// Smoke recording of the shared shell (group settings form + flash, project AI > Triggers via sidebar).
export const meta = {
  title: 'Shell smoke test',
  startRoute: '/groups/acme-corp/-/edit',
  demoTime: '2026-09-25T15:40:00-04:00',
  timezoneId: 'America/New_York',
  cursorStart: { x: 1300, y: 600 },
};

export default async function run({ page, cursor, pause, mark, caption, hideCaption, waitForIdle, goto }) {
  await pause(800);
  await caption('Settings > General', { step: 'Step 1' });
  mark('group-general');
  await cursor.click(page.getByRole('heading', { name: 'Permissions and group features' }));
  await pause(900);
  const box = page.locator('label[for="group_display_gitlab_credits_user_data"]');
  await box.scrollIntoViewIfNeeded();
  await cursor.click(box, { dx: 0.05, dy: 0.12 });
  await pause(700);
  mark('checked');
  await cursor.click(page.locator('#js-permissions-settings').getByRole('button', { name: 'Save changes' }));
  await page.waitForURL('**/groups/acme-corp/-/edit#js-permissions-settings');
  await waitForIdle();
  await cursor.sync();
  await pause(1200);
  mark('flash');
  await hideCaption();
  await goto('/acme-corp/checkout-service/-/settings/merge_requests');
  await caption('Project > Settings > Merge requests', { step: 'Step 2' });
  await pause(1200);
  mark('project-mr');
  await cursor.click(page.locator('#super-sidebar').getByRole('button', { name: 'AI' }));
  await pause(600);
  await cursor.click(page.locator('#super-sidebar').getByRole('link', { name: 'Triggers' }));
  await page.waitForURL('**/automate/triggers');
  await waitForIdle();
  await cursor.sync();
  await caption('AI > Triggers', { step: 'Step 3' });
  await page.getByText('Nightly dependency review').waitFor();
  await pause(1500);
  mark('triggers');
}

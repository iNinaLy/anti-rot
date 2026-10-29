import { test, expect } from '@playwright/test';

test('production PWA: create, attach, review offline, reload and sync', async ({ page, context }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Create an account' })).toHaveCount(0);
  expect((await page.request.post('/api/core/auth/register', {
    data: { email: 'public@example.com', password: 'must-not-be-created' },
  })).status()).toBe(404);
  await page.getByLabel('Email', { exact: true }).fill('browser@example.com');
  await page.getByLabel('Password', { exact: true }).fill('browser-test-long-password');
  await page.getByRole('button', { name: 'Sign in →', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'A little learning, every day.' })).toBeVisible();
  const cookies = await context.cookies();
  const persistentCookie = cookies.find(cookie => cookie.name === 'refresh_token');
  expect(persistentCookie?.httpOnly).toBe(true);
  expect(persistentCookie!.expires).toBeGreaterThan(Date.now() / 1000 + 86400);
  // Simulate a browser restart: keep its persistent cookie, remove JS session data.
  await page.evaluate(() => { sessionStorage.clear(); localStorage.removeItem('user'); });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'A little learning, every day.' })).toBeVisible();
  const secondTab = await context.newPage();
  await page.evaluate(() => sessionStorage.clear());
  await Promise.all([page.reload(), secondTab.goto('/')]);
  await expect(secondTab.getByRole('heading', { name: 'A little learning, every day.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'A little learning, every day.' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Reconnect your account' })).toHaveCount(0);
  await expect(secondTab.getByRole('dialog', { name: 'Reconnect your account' })).toHaveCount(0);
  await secondTab.close();
  await page.getByRole('button', { name: '+ New deck' }).click();
  await page.getByLabel('Deck name').fill('Everyday discoveries');
  for (const subject of [
    'ITT585 – Network Infrastructure Security',
    'ITT610 – Network Security / Security Analysis',
    'ICT652 – Ethical, Social and Professional Issues in ICT',
    'ITT640 – Wireless Networks',
    'ITT593 – Introduction to Digital Forensics',
  ]) await expect(page.getByRole('option', { name: subject, exact: true })).toHaveCount(1);
  await page.getByLabel('University subject').selectOption('ITT585 – Network Infrastructure Security');
  await page.getByLabel('Description').fill('A small collection of useful things to remember.');
  await page.getByRole('button', { name: 'Save deck →' }).click();
  await page.getByRole('button', { name: 'Everyday discoveries', exact: true }).click();
  await page.getByRole('button', { name: 'Edit deck', exact: true }).click();
  await expect(page.getByLabel('University subject')).toHaveValue('ITT585 – Network Infrastructure Security');
  await page.getByLabel('University subject').selectOption({ label: '+ Add subject…' });
  await page.getByLabel('New subject', { exact: true }).fill('UNI101 · Study skills');
  await page.getByRole('button', { name: 'Add subject', exact: true }).click();
  await expect(page.getByLabel('University subject')).toHaveValue('UNI101 · Study skills');
  await page.getByRole('button', { name: 'Save deck →' }).click();
  await page.getByRole('button', { name: '+ Add card' }).click();
  await page.getByLabel('Front · the prompt').fill('What makes a habit stick?');
  await page.getByLabel('Back · the answer').fill('A small, repeatable action, done consistently.');
  await page.getByRole('button', { name: 'Save card →' }).click();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.locator('dialog input[type=file]').first().setInputFiles('public/icon-192.png');
  await expect(page.locator('dialog img')).toBeVisible();
  await page.getByRole('button', { name: 'Save card →' }).click();
  await page.getByRole('button', { name: 'Start quick session →' }).click();
  await expect(page.getByText('Session saved for offline review.')).toBeVisible();
  await expect(page.locator('.review-card img')).toBeVisible();
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();
  await expect(page.getByRole('button', { name: 'Reveal answer' })).toBeVisible();
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByText('What makes a habit stick?', { exact: true })).toBeVisible();
  await expect(page.locator('.review-card img')).toBeVisible();
  await page.getByRole('button', { name: 'Reveal answer' }).click();
  await expect(page.getByText('A small, repeatable action, done consistently.', { exact: true })).toBeVisible();
  await page.screenshot({ path: '../artifacts/review-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '../artifacts/review-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('button', { name: 'Good', exact: true }).click();
  await expect(page.getByText('That’s a session in the books.')).toBeVisible();
  // Simulate expired credentials while preserving the durable offline queue.
  await context.clearCookies();
  await page.evaluate(() => sessionStorage.setItem('access', 'expired-token'));
  await page.reload();
  await expect(page.getByText('That’s a session in the books.')).toBeVisible();
  await context.setOffline(false);
  await expect(page.getByRole('dialog', { name: 'Reconnect your account' })).toBeVisible();
  await page.getByRole('dialog').getByLabel('Password').fill('browser-test-long-password');
  await page.getByRole('button', { name: 'Reconnect and sync →' }).click();
  await expect(page.getByRole('button', { name: 'All changes synced' })).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: 'Back to my day →' }).click();
  await expect(page.getByRole('region', { name: 'UNI101 · Study skills decks', exact: true })).toBeVisible();
  await expect(page.getByText('1 review session completed today')).toBeVisible();
  // FSRS Good on a new card schedules its next learning step in 10 minutes.
  await expect(page.getByText('1 due today', { exact: true })).toBeVisible();
  await page.screenshot({ path: '../artifacts/dashboard-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '../artifacts/dashboard-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('button', { name: 'Everyday discoveries', exact: true }).click();
  page.on('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Delete this deck' }).click();
  await expect(page.getByRole('button', { name: 'Create your first deck' })).toBeVisible();
  await page.getByRole('button', { name: '+ New deck' }).click();
  await expect(page.getByRole('option', { name: 'UNI101 · Study skills', exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('button', { name: 'Sign in →', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Sign in →', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('exercise defaults, day selection, completion and notification settings', async ({ page, context }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.com');
  await page.getByLabel('Password', { exact: true }).fill('browser-test-long-password');
  await page.getByRole('button', { name: 'Sign in →', exact: true }).click();
  await page.getByRole('button', { name: 'Open exercise', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Exercise', exact: true })).toBeVisible();
  await expect(page.getByLabel('Next challenge day')).toHaveValue('1');
  await expect(page.getByLabel('Reminder time')).toHaveValue('20:00');
  for (const day of ['Tuesday', 'Friday', 'Sunday']) await expect(page.getByLabel(day, { exact: true })).toBeChecked();
  for (const day of ['Monday', 'Wednesday', 'Thursday', 'Saturday']) await expect(page.getByLabel(day, { exact: true })).not.toBeChecked();
  await expect(page.getByRole('link', { name: 'YouTube playlist' })).toHaveAttribute('href', /PLpa0d6IJAhbgN8nyV8BK-GqN_A8CXgu9c/);
  await page.getByLabel('Next challenge day').selectOption('7');
  await page.getByLabel('Reminder time').fill('21:15');
  for (const day of ['Monday', 'Wednesday', 'Thursday', 'Saturday']) await page.getByLabel(day, { exact: true }).check();
  await page.getByRole('button', { name: 'Save exercise settings', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Settings saved.');
  await page.getByRole('checkbox', { name: 'Complete Day 7', exact: true }).click();
  await expect(page.getByLabel('Next challenge day')).toHaveValue('8');
  await expect(page.getByRole('checkbox', { name: 'Complete Day 7', exact: true })).toBeChecked();
  await page.reload();
  await expect(page.getByLabel('Next challenge day')).toHaveValue('8');
  await expect(page.getByLabel('Reminder time')).toHaveValue('21:15');
  // Exercise Web Push wiring without contacting an external push provider.
  await context.grantPermissions(['notifications']);
  await page.evaluate(() => {
    const data = { endpoint: 'https://fcm.googleapis.com/fcm/send/browser-test', keys: {
      p256dh: btoa(String.fromCharCode(4) + 'x'.repeat(64)).replace(/=/g, ''),
      auth: btoa('x'.repeat(16)).replace(/=/g, ''),
    } };
    const fake = { toJSON: () => data, options: {}, unsubscribe: async () => true };
    PushManager.prototype.getSubscription = async () => null;
    PushManager.prototype.subscribe = async () => fake as unknown as PushSubscription;
  });
  await page.getByRole('button', { name: 'Enable device notifications', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Notifications enabled on this device.');
  await expect(page.getByLabel('Reminders enabled', { exact: true })).toBeChecked();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../artifacts/exercise-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: '../artifacts/exercise-desktop.png', fullPage: true });
});

test('news is finite, grouped, readable and configurable without consumption rewards', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.com');
  await page.getByLabel('Password', { exact: true }).fill('browser-test-long-password');
  await page.getByRole('button', { name: 'Sign in →', exact: true }).click();
  await page.getByRole('button', { name: 'Open news', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Daily briefing', exact: true })).toBeVisible();
  await expect(page.locator('.news-story')).toHaveCount(8);
  await expect(page.locator('.story-category.malaysia').first()).toBeVisible();
  await expect(page.locator('.story-category.world').first()).toBeVisible();
  await expect(page.locator('.story-category.discovery').first()).toBeVisible();
  for (let index = 1; index <= 8; index++) {
    await page.getByRole('checkbox', { name: `Mark story ${index} read`, exact: true }).click();
    await expect(page.getByRole('checkbox', { name: `Mark story ${index} read`, exact: true })).toBeChecked();
  }
  await expect(page.getByRole('heading', { name: 'You’re caught up.', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator('.news-story')).toHaveCount(8);
  await expect(page.getByRole('heading', { name: 'You’re caught up.', exact: true })).toBeVisible();
  await page.getByText('Briefing preferences', { exact: true }).click();
  await page.getByLabel('Stories per day').selectOption('5');
  await page.getByRole('button', { name: 'Save news preferences', exact: true }).click();
  await expect(page.locator('.news-story')).toHaveCount(5);
  await expect(page.getByLabel('Reduce crime coverage')).toBeChecked();
  await page.screenshot({ path: '../artifacts/news-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../artifacts/news-mobile.png', fullPage: true });
});

test('tags, multiple choice, reviewed AI drafts and rewards', async ({ page }) => {
  page.on('dialog', dialog => dialog.accept());
  await page.goto('/');
  await page.getByLabel('Email', { exact:true }).fill('browser@example.com');
  await page.getByLabel('Password', { exact:true }).fill('browser-test-long-password');
  await page.getByRole('button', { name:'Sign in →', exact:true }).click();
  await page.getByRole('button', { name:'+ New deck', exact:true }).click();
  await page.getByLabel('Deck name').fill('Security lab');
  await page.getByRole('button', { name:'Save deck →', exact:true }).click();
  await page.getByRole('button', { name:'Security lab', exact:true }).click();
  await page.getByRole('button', { name:'+ Add card', exact:true }).click();
  await page.getByLabel('Front · the prompt').fill('Which protocol encrypts web traffic?');
  await page.getByLabel('Back · the answer').fill('TLS');
  await page.getByLabel('Tags / topics').fill('security, week-1');
  await page.getByLabel('Multiple-choice answers').fill('TLS\nFTP\nHTTP');
  await page.getByRole('button', { name:'Save card →', exact:true }).click();
  await page.getByLabel('Filter by tag or topic').selectOption('security');
  await expect(page.locator('.card-row')).toHaveCount(1);
  await page.getByRole('button', { name:'Start quick session →', exact:true }).click();
  await page.getByLabel('Review mode').selectOption('choice');
  await page.getByRole('button', { name:'TLS', exact:true }).click();
  await expect(page.getByText('Correct.', {exact:true})).toBeVisible();
  await page.getByRole('button', { name:'Good', exact:true }).click();
  await page.getByRole('button', { name:'Back to my day →', exact:true }).click();
  await expect(page.getByRole('button', { name:'All changes synced', exact:true })).toBeVisible();
  await page.getByRole('button', { name:'Security lab', exact:true }).click();
  await page.getByText('Generate flashcard drafts from notes or PDF', {exact:true}).click();
  await page.getByLabel('Source notes').fill('TLS encrypts network traffic and authenticates a server using certificates.');
  await page.route('**/api/flashcards/drafts', route => route.fulfill({ json:{ cards:[{front:'What authenticates a TLS server?',back:'A certificate',tags:['security'],choices:[]}] } }));
  await page.getByRole('button', { name:'Generate drafts', exact:true }).click();
  await expect(page.getByLabel('Keep draft 1')).toBeChecked();
  await expect(page.locator('.card-row')).toHaveCount(1);
  await page.getByRole('button', { name:'Save reviewed drafts', exact:true }).click();
  await expect(page.locator('.card-row')).toHaveCount(2);
  await page.getByRole('button', {name:'Rewards',exact:true}).click();
  await page.getByLabel('Reward name').fill('Tea break');
  await page.getByLabel('Point cost').fill('1');
  await page.getByRole('button',{name:'Save reward',exact:true}).click();
  await page.getByRole('button',{name:'Redeem',exact:true}).click();
  await expect(page.locator('.reward-history')).toContainText('Tea break');
  await expect(page.locator('.activity-heatmap > span')).toHaveCount(365);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'../artifacts/rewards-mobile.png',fullPage:true});
});

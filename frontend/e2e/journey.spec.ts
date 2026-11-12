import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
const fixture = JSON.parse(
  readFileSync(process.env.PAWTEL_E2E_FIXTURE!, 'utf8'),
);
async function login(page: Page, host = false) {
  await page.goto('/login');
  await page
    .getByLabel('Email address')
    .fill(host ? fixture.host_email : fixture.owner_email);
  await page.getByLabel('Password', { exact: true }).fill(fixture.password);
  // Keyboard submission exercises the real accessible form without pointer stability races.
  const submit = page.getByRole('button', { name: 'Log in', exact: true });
  await expect(submit).toBeEnabled();
  await submit.press('Enter');
  await expect(page).toHaveURL(/\/stays/);
}
async function logout(page: Page) {
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page.getByRole('button', { name: 'Log out', exact: true }).click();
  // Wait for anonymous navigation: private-route guards may redirect to login.
  // The account-menu button is also visible while logout is still pending.
  await expect(page).toHaveURL((url) => ['/', '/login'].includes(url.pathname));
  await expect(
    page.getByRole('button', { name: 'Account menu' }),
  ).toHaveAttribute('aria-expanded', 'false');
  await expect(
    page.getByRole('button', { name: 'Account menu' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Account menu' }).click();
  await expect(
    page.getByRole('link', { name: 'Log in', exact: true }),
  ).toBeVisible();
  await page.keyboard.press('Escape');
}
test('Owner requests a real stay, Host accepts, Owner sees awaiting payment', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText(
    'A little holiday',
  );
  await login(page);
  await page.getByLabel('Where', { exact: true }).fill(fixture.suburb);
  await page.getByRole('button', { name: 'Search stays', exact: true }).click();
  await page.getByRole('heading', { name: fixture.title, exact: true }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    fixture.title,
  );
  const start = new Date();
  start.setUTCDate(start.getUTCDate() + 10);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 2);
  await page
    .getByLabel('Check in', { exact: true })
    .fill(start.toISOString().slice(0, 10));
  await page
    .getByLabel('Check out', { exact: true })
    .fill(end.toISOString().slice(0, 10));
  await page.getByLabel('E2E Milo · Dog').check();
  await page
    .getByRole('button', { name: 'Request booking', exact: true })
    .click();
  await expect(page).toHaveURL(/\/account\/bookings\/[a-f0-9-]+$/);
  const bookingURL = page.url();
  await expect(
    page.getByRole('heading', { name: 'Waiting for the Host to respond' }),
  ).toBeVisible();
  await logout(page);
  await login(page, true);
  await page.goto('/host/bookings');
  await page.getByRole('link', { name: fixture.title, exact: true }).click();
  await page
    .getByRole('button', { name: 'Accept request', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Payment required', exact: true }),
  ).toBeVisible();
  await logout(page);
  await login(page);
  await page.goto(bookingURL);
  await expect(
    page.getByRole('heading', { name: 'Payment required', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Pay securely' })).toBeVisible();
});
test('anonymous private-page guard and real Pet creation', async ({ page }) => {
  await page.goto('/account/pets');
  await expect(page).toHaveURL(/\/login\?next=/);
  await login(page);
  await page.goto('/account/pets');
  await page.getByRole('button', { name: 'Add a pet', exact: true }).click();
  await page.getByLabel('Pet name', { exact: true }).fill('E2E Luna');
  await page
    .getByRole('combobox', { name: 'Species', exact: true })
    .selectOption('CAT');
  await page.getByRole('button', { name: 'Save pet', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'E2E Luna', exact: true }),
  ).toBeVisible();
});
test('Host draft is private until published through the website', async ({
  page,
}) => {
  await login(page, true);
  await page.goto('/host/listings/new');
  const title = `Draft ${fixture.run}`;
  await page.getByLabel('Listing title', { exact: true }).fill(title);
  await page
    .getByLabel('Description', { exact: true })
    .fill('Synthetic E2E draft.');
  await page.getByLabel('Suburb', { exact: true }).fill(fixture.suburb);
  await page.getByLabel('Postcode', { exact: true }).fill('5067');
  await page
    .getByLabel('Base nightly price (AUD)', { exact: true })
    .fill('55.00');
  await page.getByLabel('Dogs', { exact: true }).check();
  await page.getByRole('button', { name: 'Create draft', exact: true }).click();
  await expect(page).toHaveURL(/\/host\/listings\/[a-f0-9-]+\/edit$/);
  const editor = page.url();
  await page.goto(`/stays?suburb=${encodeURIComponent(fixture.suburb)}`);
  await expect(
    page.getByRole('heading', { name: fixture.title, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: title, exact: true }),
  ).toHaveCount(0);
  await page.goto(editor);
  await page
    .getByRole('button', { name: 'Publish listing', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Move to draft', exact: true }),
  ).toBeVisible();
  await page.goto(`/stays?suburb=${encodeURIComponent(fixture.suburb)}`);
  await expect(
    page.getByRole('heading', { name: title, exact: true }),
  ).toBeVisible();
});

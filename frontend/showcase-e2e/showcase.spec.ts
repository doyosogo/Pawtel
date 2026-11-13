import { readFileSync, readdirSync } from 'node:fs';
import { test, expect } from '@playwright/test';
test.beforeAll(() => {
  const scripts = readdirSync('dist/assets').filter((name) =>
    name.endsWith('.js'),
  );
  for (const script of scripts)
    expect(readFileSync(`dist/assets/${script}`, 'utf8')).not.toContain(
      'https://js.stripe.com',
    );
});
// Observe, never intercept/mock internal APIs: any non-static request fails the test.
test.beforeEach(async ({ context, page }) => {
  const forbidden: string[] = [];
  const errors: string[] = [];
  context.on('request', (request) => {
    const url = new URL(request.url());
    if (
      url.origin !== 'http://127.0.0.1:4177' ||
      url.pathname.startsWith('/api') ||
      !['GET', 'HEAD'].includes(request.method())
    )
      forbidden.push(request.url());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.exposeFunction('recordShowcaseNetworkAttempt', () =>
    forbidden.push('fetch/XHR attempt'),
  );
  await page.addInitScript(() => {
    // Covers attempted calls too, even if a restrictive CSP blocks the request.
    Object.assign(window, { showcaseNetworkCalls: 0 });
    const forbiddenCall = () => {
      (window as unknown as { showcaseNetworkCalls: number })
        .showcaseNetworkCalls++;
      void (
        window as unknown as {
          recordShowcaseNetworkAttempt: () => Promise<void>;
        }
      ).recordShowcaseNetworkAttempt();
      throw new Error('Showcase attempted network API access');
    };
    window.fetch = forbiddenCall;
    XMLHttpRequest.prototype.open = forbiddenCall;
  });
  const shell = await page.goto('/');
  expect(shell?.headers()['content-security-policy']).toContain(
    "connect-src 'none'",
  );
  await expect(page.getByLabel('Frontend showcase')).toBeVisible();
  // Assertions are also run after the journey via this test-scoped teardown.
  test.info().annotations.push({
    type: 'network-policy',
    description: 'Static same-origin GETs only; fetch/XHR forbidden',
  });
  // Keep observed evidence on the test context without writing browser artifacts.
  Object.assign(page, {
    showcaseForbidden: forbidden,
    showcasePageErrors: errors,
  });
});
test.afterEach(async ({ page }) => {
  const evidence = page as typeof page & {
    showcaseForbidden: string[];
    showcasePageErrors: string[];
  };
  expect(evidence.showcaseForbidden).toEqual([]);
  expect(evidence.showcasePageErrors).toEqual([]);
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { showcaseNetworkCalls: number })
          .showcaseNetworkCalls,
    ),
  ).toBe(0);
  const storage = await page.evaluate(() => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: [], session: [], cookie: '' });
});
test('public search, pagination, empty results and direct Listing gallery', async ({
  page,
}) => {
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.getByRole('link', { name: 'Find a stay', exact: true }).click();
  await expect(
    page.getByRole('link', { name: 'Coastal calm for little companions' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(
    page.getByRole('link', { name: 'A cosy Sydney terrace' }),
  ).toBeVisible();
  await page.getByLabel('Where', { exact: true }).fill('Glenelg');
  await page.getByRole('button', { name: 'Search stays', exact: true }).click();
  await page
    .getByRole('link', { name: 'Coastal calm for little companions' })
    .click();
  await expect(
    page.getByRole('heading', {
      name: 'Coastal calm for little companions',
      level: 1,
    }),
  ).toBeVisible();
  await expect(page.locator('main img').first()).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole('heading', {
      name: 'Coastal calm for little companions',
      level: 1,
    }),
  ).toBeVisible();
  await page.goto('/stays?suburb=Nowhere');
  await expect(page.getByText(/No stays/i).first()).toBeVisible();
});
test('Owner request → Host accept → Owner payment preview, without backend or providers', async ({
  page,
}) => {
  await page
    .getByRole('button', { name: 'Explore as Owner', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'My Pets', exact: true }),
  ).toBeVisible();
  // Client-side navigation preserves the deliberately in-memory fixture changes.
  await page.getByRole('link', { name: 'Find a stay', exact: true }).click();
  await page
    .getByRole('link', { name: 'Coastal calm for little companions' })
    .click();
  await expect(
    page.getByRole('heading', {
      name: 'Coastal calm for little companions',
      level: 1,
    }),
  ).toBeVisible();
  const date = new Date();
  date.setDate(date.getDate() + 60);
  const start = date.toISOString().slice(0, 10);
  date.setDate(date.getDate() + 3);
  const end = date.toISOString().slice(0, 10);
  await page.getByLabel('Check in', { exact: true }).fill(start);
  await expect(page.getByLabel('Check in', { exact: true })).toHaveValue(start);
  await page.getByLabel('Check out', { exact: true }).fill(end);
  await expect(page.getByLabel('Check in', { exact: true })).toHaveValue(start);
  await expect(page.getByLabel('Check out', { exact: true })).toHaveValue(end);
  await page.getByRole('checkbox', { name: 'Milo · Dog' }).check();
  await page
    .getByRole('button', { name: 'Request booking', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Waiting for the Host to respond' }),
  ).toBeVisible();
  const bookingId = page.url().split('/').at(-1)!;
  await page
    .getByRole('button', { name: 'Explore as Host', exact: true })
    .click();
  await page.getByRole('link', { name: 'Open booking inbox' }).click();
  await page.locator(`a[href="/host/bookings/${bookingId}"]`).click();
  await page
    .getByRole('button', { name: 'Accept request', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Payment required' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Explore as Owner', exact: true })
    .click();
  await page.getByRole('button', { name: 'Account menu' }).click();
  await page
    .locator('#account-menu')
    .getByRole('link', { name: 'My Bookings', exact: true })
    .click();
  await page.locator(`a[href="/account/bookings/${bookingId}"]`).click();
  await expect(
    page.getByRole('heading', { name: 'Payment required' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Pay securely' }).click();
  await expect(
    page.getByRole('heading', {
      name: 'Stripe checkout is disabled in the public frontend showcase.',
    }),
  ).toBeVisible();
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.locator('input')).toHaveCount(0);
  await page
    .getByRole('link', { name: 'Preview a separate confirmed example' })
    .click();
  await expect(page.getByText('Confirmed', { exact: true })).toBeVisible();
});
test('mobile navigation, private deep links and reset remain usable', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const route of [
    '/account/pets',
    '/account/bookings',
    '/host',
    '/host/listings',
    '/login',
    '/register',
  ]) {
    await page.goto(route);
    await expect(
      page.getByRole('heading', { name: 'Explore PAWTEL your way' }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page
    .getByRole('button', { name: 'Explore as Host', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Your Host workspace' }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'My Listings', exact: true })
    .first()
    .click();
  await expect(
    page.getByRole('heading', { name: 'My Listings', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Edit Listing & photos' })
    .first()
    .click();
  await expect(
    page.getByRole('button', { name: 'Upload photo' }),
  ).toBeDisabled();
  await expect(
    page.getByText(
      /Cloud upload is available in the full-stack implementation/,
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole('button', { name: 'Reset showcase' }).click();
  await expect(page).toHaveURL('/');
});

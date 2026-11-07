import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

// Every page kind, checked with axe. Serious and critical findings fail the build.
const routes = [
  '/',
  '/map/',
  '/updates/',
  '/checks/',
  '/sites/',
  '/sites/newby-island/',
  '/methods/',
  '/methods/cloud-model/',
  '/how-to-read/',
  '/data/',
];

for (const route of routes) {
  test(`no serious accessibility findings on ${route}`, async ({ page }) => {
    const response = await page.goto(route);
    expect(response?.status(), `${route} should exist`).toBeLessThan(400);
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
      .analyze();
    const serious = results.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact ?? ''),
    );
    expect(
      serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes) ${v.nodes[0]?.html.slice(0, 160) ?? ''}`),
    ).toEqual([]);
  });
}

test('the home page carries the retrospective framing', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toContainText(/retrospective/i);
  await expect(page.locator('body')).toContainText(/screening indication/i);
});

test('a site marked insufficient data is listed apart, never ranked, even with a median', async ({ page }) => {
  // In the fixture, Acme Fill carries a median but its 90% range is too wide for an estimate.
  await page.goto('/sites/');
  const ranked = page.locator('section[aria-labelledby="ranked"]');
  const thin = page.locator('section[aria-labelledby="thin"]');
  await expect(ranked).toContainText('Newby Island');
  await expect(ranked).not.toContainText('Acme');
  await expect(thin).toContainText('Acme Fill');
  await expect(thin).toContainText('too wide');
  await page.goto('/');
  const slide = page.locator('.carousel-slide', { hasText: 'Acme Fill' });
  await expect(slide).toContainText('Not enough data for an estimate');
});

test('the site stays light when the system asks for dark', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe('rgb(255, 255, 255)');
});

test('a carousel shows two slides, moves on its own, and answers its arrows and pause button', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  const carousel = page.getByRole('region', { name: 'How it works, step by step' });
  await carousel.scrollIntoViewIfNeeded();
  const active = () => carousel.locator('.carousel-dots button[aria-current="true"]').getAttribute('aria-label');
  const inView = () =>
    carousel.evaluate((root) => {
      const box = root.querySelector('.carousel-viewport')!.getBoundingClientRect();
      return [...root.querySelectorAll('.carousel-slide')].filter((s) => {
        const r = s.getBoundingClientRect();
        return r.left >= box.left - 1 && r.right <= box.right + 1;
      }).length;
    });

  await expect.poll(inView).toBe(2);
  const first = await active();
  await expect.poll(active, { timeout: 8000 }).not.toBe(first);

  const before = await active();
  await carousel.getByRole('button', { name: 'Next slide' }).click();
  await expect.poll(active).not.toBe(before);

  await carousel.getByRole('button', { name: /^Pause/ }).click();
  await page.mouse.move(0, 0);
  await page.locator('h1').click();
  const paused = await active();
  await page.waitForTimeout(6500);
  expect(await active()).toBe(paused);
});

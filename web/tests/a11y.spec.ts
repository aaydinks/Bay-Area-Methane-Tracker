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

test('dark mode toggles without a reload', async ({ page }) => {
  await page.goto('/');
  const html = page.locator('html');
  const before = await html.getAttribute('data-theme');
  await page.getByRole('button', { name: /theme/i }).click();
  const after = await html.getAttribute('data-theme');
  expect(after).not.toBe(before);
});

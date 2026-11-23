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
  const card = page.locator('.site-card', { hasText: 'Acme Fill' });
  await expect(card).toContainText('Not enough data yet');
  await expect(card).not.toContainText(/t\/yr|tonnes/);
});

test('the site stays light when the system asks for dark', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe('rgb(255, 255, 255)');
});

test('the home page has one main next step and no moving carousels', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('main .button.primary')).toHaveCount(1);
  await expect(page.locator('.steps > li')).toHaveCount(3);
  await expect(page.locator('.carousel')).toHaveCount(0);
});

test('the map steps through plumes month by month', async ({ page }) => {
  await page.goto('/map/');
  const load = page.getByRole('button', { name: 'Load the map now' });
  // The map may start loading on its own as it scrolls into view, so the button can vanish.
  if (await load.isVisible()) await load.click({ timeout: 3000 }).catch(() => undefined);
  const label = page.locator('.timeline-label');
  await expect(label).toContainText(/All dates, \w{3} \d{4} to \w{3} \d{4} · \d+ plumes? seen, \d+ traced to the landfills/);
  await page.getByLabel('By month').check();
  const slider = page.locator('.timeline-slider');
  await expect(slider).toBeVisible();
  await expect(label).toContainText(/^[A-Z][a-z]+ \d{4} · \d+ plumes? seen, \d+ traced to the landfills/);
  const first = await label.textContent();
  await slider.fill(await slider.getAttribute('max') ?? '1');
  await expect(label).not.toHaveText(first ?? '');
  await page.getByLabel('By quarter').check();
  await expect(label).toContainText(/^[A-Z][a-z]{2} to [A-Z][a-z]{2} \d{4} · \d+ plumes? seen, \d+ traced to the landfills/);
  const play = page.locator('.timeline .play');
  await play.click();
  await expect(play).toHaveAttribute('aria-pressed', 'true');
  await play.click();
  await expect(play).toHaveAttribute('aria-pressed', 'false');
  // The filters and the full key stay one click away, closed at first.
  await expect(page.locator('details.map-more')).not.toHaveAttribute('open', '');
  // The loaded map and its timeline pass the same accessibility scan as the pages.
  await page.locator('details.map-more summary').click();
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  const serious = results.violations.filter((v) => ['serious', 'critical'].includes(v.impact ?? ''));
  expect(serious.map((v) => `${v.id}: ${v.help} ${v.nodes[0]?.html.slice(0, 160) ?? ''}`)).toEqual([]);
});

test('the map and site pages lead with one sentence and keep the notices', async ({ page }) => {
  for (const route of ['/map/', '/sites/newby-island/']) {
    await page.goto(route);
    await expect(page.locator('main .lede')).toHaveCount(1);
    await expect(page.locator('.banner', { hasText: 'Provisional' })).toHaveCount(1);
    await expect(page.locator('body')).toContainText(/screening indication/i);
    await expect(page.locator('main details.more').first()).toBeAttached();
  }
  await page.goto('/sites/newby-island/');
  await expect(page.locator('.headline-figure')).toContainText('tonnes a year');
  await expect(page.locator('[data-testid="model-instruments"]')).toBeHidden();
});

test('reported figures show a gap as "not reported", never as zero', async ({ page }) => {
  // In the fixture, Potrero Hills has a landfill figure for 2023 and one combustion figure for
  // 2018, so each year has one measure with no figure; Shoreline has nothing on file.
  await page.goto('/sites/potrero-hills/');
  const section = page.locator('#reported');
  await section.locator('summary').click();
  const rows = section.locator('tbody tr');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toHaveText(/2023\s*30,862\s*not reported/);
  await expect(rows.nth(1)).toHaveText(/2018\s*not reported\s*412/);
  await expect(section.locator('caption')).toContainText('It does not mean zero');
  await expect(section).toContainText('Not reported for this landfill in any year: Biogenic CO2');
  const results = await new AxeBuilder({ page }).include('#reported').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  expect(results.violations.filter((v) => ['serious', 'critical'].includes(v.impact ?? '')).map((v) => v.id)).toEqual([]);

  await page.goto('/sites/shoreline/');
  const empty = page.locator('#reported');
  await empty.locator('summary').click();
  await expect(empty.locator('table')).toHaveCount(0);
  await expect(empty).toContainText('No figures from this source are on file for this landfill');
});

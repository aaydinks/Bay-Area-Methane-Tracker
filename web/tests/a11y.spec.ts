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
  '/sites/kiefer/',
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

test('a site marked insufficient data shows no figure and is never ranked, even with a median', async ({ page }) => {
  // In the fixture, Acme Fill carries a median but its 90% range is too wide for an estimate.
  await page.goto('/sites/');
  const ranked = page.locator('section[aria-labelledby="ranked"]');
  await expect(ranked).toContainText('Newby Island');
  await expect(ranked).not.toContainText('Acme');
  const row = page.locator('.sites-table tbody tr', { hasText: 'Acme Fill' });
  await expect(row).toContainText('Not enough data yet');
  await expect(row).toContainText('too wide');
  await expect(row).not.toContainText('t/yr');
  // Sorting by the estimate, either way, keeps every landfill without one after the ranked ones.
  const names = () => page.locator('.sites-table tbody tr th a').allTextContents();
  const sort = page.locator('.sites-table th button', { hasText: 'Estimate' });
  expect((await names()).slice(0, 2)).toEqual(['Newby Island Landfill', 'Potrero Hills Landfill']);
  await sort.click();
  await expect(page.locator('.sites-table th[aria-sort="ascending"]')).toContainText('Estimate');
  expect((await names()).slice(0, 4)).toEqual(['Altamont Landfill', 'Potrero Hills Landfill', 'Newby Island Landfill', 'Acme Fill']);
  await page.goto('/');
  const card = page.locator('.site-card', { hasText: 'Acme Fill' });
  await expect(card).toContainText('Not enough data yet');
  await expect(card).not.toContainText(/t\/yr|tonnes/);
});

test('the landfills table filters by region and by how closely a landfill is followed', async ({ page }) => {
  // The review fixture holds five landfills studied in depth and four screened, in two regions.
  await page.goto('/sites/');
  await expect(page.locator('main .lede')).toHaveText('Nine landfills in the Bay Area and the North Valley: five studied in depth, the rest screened with the same public data.');
  const rows = page.locator('.sites-table tbody tr');
  const count = page.locator('.sites-count');
  await expect(rows).toHaveCount(9);
  await expect(count).toHaveText('9 of 9 landfills shown, 3 with an estimate.');
  await page.locator('.sites-filters label', { hasText: 'Region' }).locator('select').selectOption({ label: 'North Valley' });
  await expect(rows).toHaveCount(2);
  await expect(count).toHaveText('2 of 9 landfills shown, 0 with an estimate.');
  await expect(rows.first()).toContainText('No estimate yet');
  await page.locator('.sites-filters label', { hasText: 'Region' }).locator('select').selectOption({ label: 'All regions' });
  await page.locator('.sites-filters label', { hasText: 'Show' }).locator('select').selectOption({ label: 'Studied in depth' });
  await expect(rows).toHaveCount(5);
  await page.locator('.sites-table th button', { hasText: 'Plume days' }).click();
  await expect(page.locator('.sites-table th[aria-sort="descending"]')).toContainText('Plume days');
  await expect(rows.first()).toContainText('Newby Island');
  // A phone gets the same landfills as a list, with no sideways scroll of the page.
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.locator('.sites-table')).toBeHidden();
  await expect(page.locator('.sites-cards li')).toHaveCount(5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('the home page counts its landfills from the data and shows cards for those studied in depth', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.hero .lede')).toHaveText('A look back at what satellites have seen of methane coming from nine landfills in the Bay Area and the North Valley.');
  await expect(page.locator('#landfills')).toHaveText('The five landfills studied in depth');
  await expect(page.locator('.site-card')).toHaveCount(5);
  await expect(page.locator('.site-card', { hasText: 'Kiefer' })).toHaveCount(0);
  await expect(page.locator('[data-testid="screened-note"]')).toContainText('Four more landfills are screened with the same public data.');
});

test('a screened landfill says it has no estimate yet, and why', async ({ page }) => {
  await page.goto('/sites/kiefer/');
  await expect(page.locator('main .lede')).toContainText('This landfill is screened');
  const estimate = page.locator('section[aria-labelledby="estimate"]');
  await expect(estimate).toContainText('No estimate yet');
  await expect(estimate).toContainText('not yet part of a model fit');
  await expect(estimate).not.toContainText('Insufficient data');
  await expect(page.locator('.headline-figure')).toHaveCount(0);
});

test('a figure from the screening fit says so wherever it is shown', async ({ page }) => {
  // In the fixture a screening fit supplies Altamont's figure and marks Keller Canyon as
  // insufficient data; the landfills studied in depth keep the main fit's figures.
  await page.goto('/sites/altamont/');
  const note = page.locator('[data-testid="screening-fit"]');
  await expect(note).toContainText('This figure comes from the screening fit, one model fitted to all 7 landfills together.');
  await expect(note).toContainText('provisional');
  await expect(page.locator('.figure-range')).toContainText('provisional');
  await page.goto('/sites/newby-island/');
  await expect(page.locator('.headline-figure')).toHaveCount(1);
  await expect(page.locator('[data-testid="screening-fit"]')).toHaveCount(0);
  await page.goto('/sites/keller-canyon/');
  await expect(page.locator('section[aria-labelledby="estimate"]')).toContainText('Insufficient data');
  await expect(page.locator('.headline-figure')).toHaveCount(0);

  await page.goto('/sites/');
  await expect(page.locator('.sites-table tbody tr', { hasText: 'Altamont' })).toContainText('screening fit');
  await expect(page.locator('.sites-table tbody tr', { hasText: 'Newby Island' })).not.toContainText('screening fit');
  await expect(page.locator('[data-testid="chart-fits"]')).toContainText('Figures for screened landfills come from the screening fit');
  await page.locator('summary', { hasText: 'What the estimates mean' }).click();
  await expect(page.locator('[data-testid="screening-fit-note"]')).toContainText('one model fitted to all seven landfills together');
  await page.goto('/methods/');
  await expect(page.locator('[data-testid="two-fits"]')).toContainText('Two model fits sit side by side.');
  await expect(page.locator('[data-testid="two-fits"]')).toContainText('with a term that lets the regions differ');
});

test('a record names the air district its landfill falls under', async ({ page }) => {
  // The fixture has records at landfills in two air districts.
  await page.goto('/checks/');
  const table = page.locator('.checks-table');
  await expect(table.locator('tbody tr', { hasText: 'Sonoma Central' })).toContainText('Bay Area AQMD notice');
  await expect(table.locator('tbody tr', { hasText: 'Kiefer' })).toContainText('Sacramento Metro AQMD inspection');
  await expect(table).not.toContainText('Air District');
  await page.goto('/sites/kiefer/');
  await expect(page.locator('section[aria-labelledby="checks"]')).toContainText('Sacramento Metro AQMD inspection');
  await expect(page.locator('[data-testid="air-district"]')).toHaveText("Sacramento Metro AQMD (from CARB's 2004 district outlines; not yet checked with the district)");
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
  // One region at a time: its landfills only, and the plumes that go with them. The counts
  // come from the data, so this holds whether or not the basemap has loaded.
  const everywhere = await label.textContent();
  await page.getByLabel('North Valley', { exact: true }).check();
  await expect(label).toContainText(/All dates, \w{3} \d{4} to \w{3} \d{4} · \d+ plumes? seen, \d+ traced to the landfills/);
  await expect(label).not.toHaveText(everywhere ?? '');
  await page.getByLabel('All regions', { exact: true }).check();
  await expect(label).toHaveText(everywhere ?? '');
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

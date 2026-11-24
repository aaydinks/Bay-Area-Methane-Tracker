// The published snapshot the whole site is built from. Written by scripts/fetch-data.mjs at
// build time; pages import this module and never query anything at run time.

import { AIR_DISTRICT, CHECK_TYPE, REGION } from '../config';
import type { Database } from './database.types';
import { countWord, listText } from './format';
import snapshotJson from '../data/snapshot.json';

type Views = Database['public']['Views'];
type Tables = Database['public']['Tables'];

export type Publication = Tables['publications']['Row'];
export type Run = Tables['runs']['Row'];
export type DataTerm = Tables['data_terms']['Row'];
export type Site = Views['v_sites']['Row'];
export type Neighbour = Views['v_neighbours']['Row'];
export type Plume = Views['v_plumes']['Row'];
export type PassMonth = Views['v_pass_months']['Row'];
export type PlumeDays = Views['v_plume_days']['Row'];
export type SiteEstimate = Tables['site_estimates']['Row'];
export type CheckWithResult = Views['v_checks_with_results']['Row'] & { result_held?: boolean };
export type OperatorReport = Tables['operator_reports']['Row'];
export type Population = Tables['population_context']['Row'];
export type SiteFeature = Tables['site_features']['Row'];
export type SiteMetric = Tables['site_metrics']['Row'];
export type MetricEntry = Tables['metric_catalogue']['Row'];
export type ValidationResult = Tables['validation_results']['Row'];
export type UpdateLogItem = Tables['update_log']['Row'];
export type Boundary = Views['v_boundaries']['Row'];

export interface Meta {
  site_mode: 'review' | 'public';
  data_source: 'fixture' | 'supabase';
  fetched_at: string;
  site_url: string;
  counts: Record<string, number>;
  downloads?: { file: string; name: string; rows: number }[];
}

export interface Snapshot {
  meta: Meta;
  publication: Publication | null;
  publications: Publication[];
  runs: Run[];
  data_terms: DataTerm[];
  boundaries: Boundary[];
  update_log: UpdateLogItem[];
  sites: Site[];
  neighbours: Neighbour[];
  plumes: Plume[];
  pass_months: PassMonth[];
  plume_days: PlumeDays[];
  site_estimates: SiteEstimate[];
  checks: CheckWithResult[];
  operator_reports: OperatorReport[];
  population: Population[];
  site_features: SiteFeature[];
  site_metrics?: SiteMetric[];
  metric_catalogue?: MetricEntry[];
  validation_results: ValidationResult[];
}

export const snapshot = snapshotJson as unknown as Snapshot;
export const meta = snapshot.meta;
export const publication = snapshot.publication;
export const isPublic = meta.site_mode === 'public';
export const isFixture = meta.data_source === 'fixture';
export const hasPublication = publication !== null;

export const sites = [...snapshot.sites].sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''));

// ---- regions and tiers (ADR 0018) -----------------------------------------------------------
// Every count and place name on the pages comes from the sites this build holds, so a public
// build names only the regions it shows.

export const regionLabel = (id: string | null | undefined): string => (id ? (REGION[id] ?? id) : '');

/** Regions with at least one landfill in this build, in the order config.ts lists them. */
export const regionIds: string[] = [
  ...Object.keys(REGION),
  ...[...new Set(snapshot.sites.map((s) => s.region ?? ''))].filter((r) => r && !(r in REGION)).sort(),
].filter((id) => snapshot.sites.some((s) => s.region === id));

/** "the Bay Area and the North Valley", or an empty string before the first update. */
export const regionsText = listText(regionIds.map((id) => `the ${regionLabel(id)}`));

/** "five landfills in the Bay Area": how many of them, and where. */
export function landfillsText(n: number): string {
  return `${countWord(n)} ${n === 1 ? 'landfill' : 'landfills'}${regionsText ? ` in ${regionsText}` : ''}`;
}

/** The landfills studied in depth; the rest are screened with the same public data. */
export const isStudied = (s: Site): boolean => s.tier === 'pilot';
export const studiedSites = sites.filter(isStudied);

// ---- regulators (ADR 0020) ------------------------------------------------------------------

/** A site's air district as CARB's list names it, or "<name> air district" for one not listed. */
export function districtLabel(name: string | null | undefined): string {
  return name ? (AIR_DISTRICT[name] ?? `${name} air district`) : '';
}

/** What kind of record a check is, naming the regulator where the kind has one: an air
 *  district record is from the district its landfill sits in, which the build has checked
 *  against the record itself. */
export function checkLabel(checkType: string | null | undefined, siteId: string | null | undefined): string {
  const info = CHECK_TYPE[checkType ?? 'other'] ?? CHECK_TYPE.other;
  const district = info.record && siteId ? districtLabel(siteById(siteId)?.air_district) : '';
  return district ? `${district} ${info.record}` : info.label;
}

export function siteById(siteId: string): Site | undefined {
  return snapshot.sites.find((s) => s.site_id === siteId);
}

export function siteName(siteId: string | null | undefined): string {
  return (siteId && siteById(siteId)?.name) || siteId || '';
}

export function estimateFor(siteId: string): SiteEstimate | undefined {
  return snapshot.site_estimates.find((e) => e.site_id === siteId && e.period === 'all');
}

// The estimate a page may show as a figure. A site the model marks as insufficient data can still
// carry a median (for example when its 90% range spans more than a hundredfold); that median is
// not an estimate, so it is never shown, ranked or charted.
export function usableEstimate(siteId: string): (SiteEstimate & { e_t_yr_med: number }) | undefined {
  const e = estimateFor(siteId);
  return e && e.status !== 'insufficient_data' && e.e_t_yr_med != null ? (e as SiteEstimate & { e_t_yr_med: number }) : undefined;
}

export function checksFor(siteId: string): CheckWithResult[] {
  return snapshot.checks
    .filter((c) => c.site_id === siteId)
    .sort((a, b) => (a.date_start ?? '').localeCompare(b.date_start ?? ''));
}

export function latestCheckFor(siteId: string): CheckWithResult | undefined {
  const withResult = checksFor(siteId).filter((c) => c.colour);
  return withResult[withResult.length - 1];
}

export function plumeDaysFor(siteId: string): PlumeDays | undefined {
  return snapshot.plume_days.find((p) => p.site_id === siteId);
}

export function passMonthsFor(siteId: string): PassMonth[] {
  return snapshot.pass_months.filter((p) => p.site_id === siteId);
}

export function passesByInstrument(siteId: string): { instrument: string; passes: number; usable: number; detected: number }[] {
  const out = new Map<string, { instrument: string; passes: number; usable: number; detected: number }>();
  for (const row of passMonthsFor(siteId)) {
    const key = row.instrument ?? 'unknown';
    const g = out.get(key) ?? { instrument: key, passes: 0, usable: 0, detected: 0 };
    g.passes += row.n_passes ?? 0;
    g.usable += row.n_usable ?? 0;
    g.detected += row.n_detected ?? 0;
    out.set(key, g);
  }
  return [...out.values()].sort((a, b) => a.instrument.localeCompare(b.instrument));
}

// The model run's manifest names the instruments it used and, since decision record 0016,
// those it left out because their plume search had not run. For an older run only the gap
// between its instruments and the published passes is known, so the reason stays null.
export interface LeftOut { instrument: string; reason: string | null }
export const NOT_SEARCHED = 'plume search not run';
interface ModelManifest { instruments?: string[]; instruments_left_out?: Record<string, { reason?: string }> }

export function modelInstruments(): { used: string[]; leftOut: LeftOut[] } {
  const run = snapshot.runs.find((r) => r.run_id === publication?.model_run_id);
  const m = (run?.manifest ?? {}) as ModelManifest;
  if (!run || !m.instruments) return { used: [], leftOut: [] };
  const used = [...m.instruments].sort();
  const recorded = m.instruments_left_out ?? {};
  const leftOut: LeftOut[] = Object.entries(recorded).map(([instrument, v]) => ({ instrument, reason: v.reason ?? null }));
  const usable = new Set(snapshot.pass_months.filter((p) => (p.n_usable ?? 0) > 0).map((p) => p.instrument ?? ''));
  for (const inst of [...usable].sort()) {
    if (inst && !used.includes(inst) && !(inst in recorded)) leftOut.push({ instrument: inst, reason: null });
  }
  return { used, leftOut };
}

export function operatorReportsFor(siteId: string): OperatorReport[] {
  return snapshot.operator_reports.filter((o) => o.site_id === siteId).sort((a, b) => a.year - b.year);
}

// ---- measures beside the methane estimate (ADR 0019) ----------------------------------------

const catalogue = [...(snapshot.metric_catalogue ?? [])].sort((x, y) => x.sort_order - y.sort_order);

// A copy published before the measures existed carries no catalogue, and its pages show no
// measures section at all: an empty table there would read as "nothing was reported".
export const hasMeasures = catalogue.length > 0;

export interface MeasureGroup {
  source: string;
  sourceName: string;
  /** Measures with at least one figure for the site, in catalogue order. */
  columns: MetricEntry[];
  /** Measures the catalogue lists for this source that have no figure for the site. */
  missing: MetricEntry[];
  /** Periods with any figure, newest first. */
  periods: string[];
  /** The one unit every column shares, or null when they differ. */
  unit: string | null;
  url: string | null;
  cell: (period: string, metricId: string) => SiteMetric | undefined;
}

/** Reported figures for a site, one group per source. A measure or a year without a row is
 *  "not reported"; it is never shown as zero. */
export function reportedMeasuresFor(siteId: string): MeasureGroup[] {
  const reported = catalogue.filter((m) => m.kind === 'reported');
  const rows = (snapshot.site_metrics ?? []).filter((r) => r.site_id === siteId);
  return [...new Set(reported.map((m) => m.source))].map((source) => {
    const entries = reported.filter((m) => m.source === source);
    const ids = new Set(entries.map((m) => m.metric_id));
    const mine = rows.filter((r) => r.source === source && ids.has(r.metric_id));
    const byKey = new Map(mine.map((r) => [`${r.period}|${r.metric_id}`, r]));
    const columns = entries.filter((m) => mine.some((r) => r.metric_id === m.metric_id));
    const units = new Set(columns.map((m) => m.unit));
    return {
      source,
      sourceName: snapshot.data_terms.find((d) => d.source === source)?.display_name ?? source,
      columns,
      missing: entries.filter((m) => !columns.includes(m)),
      periods: [...new Set(mine.map((r) => r.period))].sort().reverse(),
      unit: units.size === 1 ? [...units][0] : null,
      url: mine.find((r) => r.url)?.url ?? null,
      cell: (period: string, metricId: string) => byKey.get(`${period}|${metricId}`),
    };
  });
}

export function populationFor(siteId: string): Population[] {
  return snapshot.population.filter((p) => p.site_id === siteId).sort((a, b) => a.radius_km - b.radius_km);
}

export function neighboursFor(siteId: string): Neighbour[] {
  return snapshot.neighbours.filter((n) => n.nearest_site_id === siteId);
}

export function featuresFor(siteId: string): SiteFeature | undefined {
  return snapshot.site_features.find((f) => f.site_id === siteId);
}

export const totals = {
  sites: snapshot.sites.length,
  usablePasses: snapshot.pass_months.reduce((n, p) => n + (p.n_usable ?? 0), 0),
  passes: snapshot.pass_months.reduce((n, p) => n + (p.n_passes ?? 0), 0),
  plumeDays: snapshot.plume_days.reduce((n, p) => n + (p.plume_days ?? 0), 0),
  plumes: snapshot.plumes.length,
  estimates: snapshot.sites.filter((s) => usableEstimate(s.site_id ?? '')).length,
  checks: snapshot.checks.length,
  checkResults: snapshot.checks.filter((c) => c.colour).length,
};

export const currentUpdates = publication
  ? snapshot.update_log.filter((u) => u.publish_id === publication.publish_id).sort((a, b) => a.item_order - b.item_order)
  : [];

const carbonMapperTerms = snapshot.data_terms.find((t) => t.source === 'carbonmapper');
// Display only (ADR 0017): figures built from Carbon Mapper data are shown, never downloaded.
export const carbonMapperDisplayOnly = isPublic && !!carbonMapperTerms?.confirmed && !!carbonMapperTerms?.display_publishable && !carbonMapperTerms?.derived_publishable;
export const carbonMapperHeld = isPublic && !carbonMapperDisplayOnly && !(carbonMapperTerms?.confirmed && carbonMapperTerms?.derived_publishable);

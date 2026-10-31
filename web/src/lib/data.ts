// The published snapshot the whole site is built from. Written by scripts/fetch-data.mjs at
// build time; pages import this module and never query anything at run time.

import type { Database } from './database.types';
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
  validation_results: ValidationResult[];
}

export const snapshot = snapshotJson as unknown as Snapshot;
export const meta = snapshot.meta;
export const publication = snapshot.publication;
export const isPublic = meta.site_mode === 'public';
export const isFixture = meta.data_source === 'fixture';
export const hasPublication = publication !== null;

export const sites = [...snapshot.sites].sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''));

export function siteById(siteId: string): Site | undefined {
  return snapshot.sites.find((s) => s.site_id === siteId);
}

export function siteName(siteId: string | null | undefined): string {
  return (siteId && siteById(siteId)?.name) || siteId || '';
}

export function estimateFor(siteId: string): SiteEstimate | undefined {
  return snapshot.site_estimates.find((e) => e.site_id === siteId && e.period === 'all');
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

export function operatorReportsFor(siteId: string): OperatorReport[] {
  return snapshot.operator_reports.filter((o) => o.site_id === siteId).sort((a, b) => a.year - b.year);
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
  estimates: snapshot.site_estimates.filter((e) => e.status !== 'insufficient_data').length,
  checks: snapshot.checks.length,
  checkResults: snapshot.checks.filter((c) => c.colour).length,
};

export const currentUpdates = publication
  ? snapshot.update_log.filter((u) => u.publish_id === publication.publish_id).sort((a, b) => a.item_order - b.item_order)
  : [];

export const carbonMapperHeld = isPublic && !snapshot.data_terms.some((t) => t.source === 'carbonmapper' && t.confirmed && t.derived_publishable);

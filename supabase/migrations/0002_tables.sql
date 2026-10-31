-- Tables of the publishing database.
--
-- One "publication" is a full snapshot of one run: sites, passes, plumes, estimates, checks and
-- their results, operator figures, validation results and the update log. Every content table
-- carries publish_id, so the latest-update feed is a difference of two snapshots and taking a
-- publication down is a visibility change. Rows that come from a source whose terms are not yet
-- confirmed (Carbon Mapper) carry restricted = true and never reach the public website.
--
-- Units follow the project: rates in kg/hr, annual totals in t/yr, times in UTC, geometry in
-- WGS 84 (SRID 4326).

create table public.publications (
  publish_id       text primary key,
  created_at       timestamptz not null default now(),
  visibility       text not null default 'draft'
                   check (visibility in ('draft', 'review', 'public')),
  published_at     timestamptz,
  simulated        boolean not null default false,
  provisional      boolean not null default false,
  refresh_id       text,
  model_run_id     text,
  check_run_id     text,
  data_through     date,
  source_lag_days  integer not null default 30 check (source_lag_days >= 0),
  git_sha          text,
  git_dirty        boolean,
  notes            text,
  constraint publications_simulated_never_public check (not (simulated and visibility = 'public'))
);
comment on table public.publications is
  'One row per published snapshot. Visibility decides who can see it: draft (nobody), review (the protected review build), public (the website).';

create table public.runs (
  run_id         text primary key,
  kind           text not null check (kind in ('refresh', 'model', 'repair', 'validation', 'publish')),
  created_at     timestamptz,
  git_sha        text,
  git_dirty      boolean,
  config_sha256  jsonb,
  versions       jsonb,
  manifest       jsonb not null default '{}'::jsonb
);
comment on table public.runs is 'Run manifests copied as written by the pipeline, so every figure can be traced to code and config.';

create table public.data_terms (
  source               text primary key,
  display_name         text not null,
  raw_publishable      boolean not null default false,
  derived_publishable  boolean not null default false,
  confirmed            boolean not null default false,
  checked_on           date,
  terms_url            text,
  credit_line          text
);
comment on table public.data_terms is 'What each data source allows, mirrored from DATA_TERMS.md. Drives the restricted flags.';

create table public.sites (
  publish_id          text not null references public.publications (publish_id) on delete cascade,
  site_id             text not null,
  name                text not null,
  city                text,
  county              text,
  operator            text,
  tier                text check (tier in ('pilot', 'screen')),
  status              text,
  swis_number         text,
  ghgrp_facility_id   text,
  outline             extensions.geometry(MultiPolygon, 4326),
  centroid            extensions.geometry(Point, 4326)
                      generated always as (extensions.st_centroid(outline)) stored,
  polygon_source      text,
  provisional         boolean not null default true,
  area_km2            double precision check (area_km2 is null or area_km2 > 0),
  primary key (publish_id, site_id)
);
comment on table public.sites is 'Landfills in the snapshot. provisional = the outline is a placeholder, not a traced boundary. Registry notes are internal and never loaded.';

create table public.neighbours (
  publish_id        text not null references public.publications (publish_id) on delete cascade,
  neighbour_id      text not null,
  name              text not null,
  kind              text not null check (kind in ('compost', 'wastewater', 'refinery', 'landfill', 'other')),
  geom              extensions.geometry(Geometry, 4326) not null,
  nearest_site_id   text,
  distance_m        double precision check (distance_m is null or distance_m >= 0),
  source            text,
  primary key (publish_id, neighbour_id)
);
comment on table public.neighbours is 'Other methane sources near a landfill. Plumes near one of these are flagged ambiguous, never assigned.';

create table public.plumes (
  publish_id      text not null references public.publications (publish_id) on delete cascade,
  plume_id        text not null,
  source          text not null check (source in ('carbonmapper', 'emit-v2', 's2-local')),
  instrument      text not null check (instrument in ('tanager1', 'emit', 'aircraft', 'sentinel2')),
  acquired_utc    timestamptz not null,
  lon             double precision not null check (lon between -180 and 180),
  lat             double precision not null check (lat between -90 and 90),
  geom            extensions.geometry(Point, 4326)
                  generated always as (extensions.st_setsrid(extensions.st_makepoint(lon, lat), 4326)) stored,
  q_kg_hr         double precision check (q_kg_hr is null or q_kg_hr >= 0),
  q_sigma_kg_hr   double precision check (q_sigma_kg_hr is null or q_sigma_kg_hr >= 0),
  site_id         text,
  attribution     text not null check (attribution in ('inside', 'buffer', 'ambiguous', 'nearby', 'none')),
  distance_m      double precision check (distance_m is null or distance_m >= 0),
  data_version    text,
  overpass_id     text,
  restricted      boolean not null default true,
  new_in_update   boolean not null default false,
  primary key (publish_id, source, plume_id)
);
comment on table public.plumes is 'Plume origins from every source. restricted rows come from a source whose publication terms are unconfirmed and are hidden from the public website.';

create table public.passes (
  publish_id       text not null references public.publications (publish_id) on delete cascade,
  overpass_id      text not null,
  site_id          text not null,
  instrument       text not null check (instrument in ('tanager1', 'emit', 'aircraft', 'sentinel2')),
  acquired_utc     timestamptz not null,
  usable           boolean not null,
  coverage_frac    double precision check (coverage_frac between 0 and 1),
  valid_frac       double precision check (valid_frac between 0 and 1),
  coverage_source  text check (coverage_source in ('stac-footprint', 'cmr-granule', 's2-scene', 'inferred')),
  detected         boolean not null default false,
  q_obs_kg_hr      double precision check (q_obs_kg_hr is null or q_obs_kg_hr > 0),
  n_plumes         integer not null default 0 check (n_plumes >= 0),
  restricted       boolean not null default true,
  primary key (publish_id, overpass_id)
);
comment on table public.passes is 'One row per site, instrument and observation day: the denominator. Tanager and aircraft passes come from Carbon Mapper scenes and are restricted like its plumes.';

create table public.site_estimates (
  publish_id           text not null references public.publications (publish_id) on delete cascade,
  model_run_id         text not null,
  site_id              text not null,
  period               text not null default 'all',
  n_usable_overpasses  integer not null check (n_usable_overpasses >= 0),
  n_detections         integer not null check (n_detections >= 0),
  f_med                double precision check (f_med is null or f_med between 0 and 1),
  f_lo                 double precision check (f_lo is null or f_lo between 0 and 1),
  f_hi                 double precision check (f_hi is null or f_hi between 0 and 1),
  qbar_kg_hr_med       double precision check (qbar_kg_hr_med is null or qbar_kg_hr_med >= 0),
  qbar_kg_hr_lo        double precision check (qbar_kg_hr_lo is null or qbar_kg_hr_lo >= 0),
  qbar_kg_hr_hi        double precision check (qbar_kg_hr_hi is null or qbar_kg_hr_hi >= 0),
  e_t_yr_med           double precision check (e_t_yr_med is null or e_t_yr_med >= 0),
  e_t_yr_lo            double precision check (e_t_yr_lo is null or e_t_yr_lo >= 0),
  e_t_yr_hi            double precision check (e_t_yr_hi is null or e_t_yr_hi >= 0),
  status               text not null check (status in ('estimate', 'insufficient_data', 'provisional')),
  insufficient_reason  text,
  rhat_max             double precision,
  ess_bulk_min         double precision,
  divergences          integer,
  provisional          boolean not null default false,
  restricted           boolean not null default true,
  primary key (publish_id, site_id, period)
);
comment on table public.site_estimates is 'Persistence estimates per site with 90% ranges: emitting share f, mean rate while emitting, and annual methane above the floor in daytime clear-sky conditions.';

create table public.checks (
  publish_id         text not null references public.publications (publish_id) on delete cascade,
  check_id           text not null,
  site_id            text not null,
  check_type         text not null check (check_type in (
                       'air-district-inspection', 'air-district-notice', 'operator-repair',
                       'carb-plume-notice', 'other')),
  repair_kind        text check (repair_kind is null or repair_kind in ('well-field', 'cover', 'leak-repair', 'other')),
  date_start         date not null,
  date_end           date,
  date_confidence    text not null check (date_confidence in ('exact', 'week', 'month')),
  description        text not null,
  source_doc         text not null check (length(source_doc) > 0),
  source_doc_title   text,
  source_url         text,
  source_page        text,
  entered_on         date,
  primary key (publish_id, check_id)
);
comment on table public.checks is 'Dated records at a landfill: Air District inspections and notices, operator repairs, CARB plume notices. No row without a source document.';

create table public.check_results (
  publish_id       text not null references public.publications (publish_id) on delete cascade,
  check_run_id     text not null,
  check_id         text not null,
  site_id          text not null,
  call             text not null check (call in ('drop', 'rise', 'inconclusive', 'insufficient_data')),
  effect_med       double precision,
  effect_lo        double precision,
  effect_hi        double precision,
  change_pct_med   double precision,
  change_pct_lo    double precision,
  change_pct_hi    double precision,
  de_t_yr_med      double precision,
  de_t_yr_lo       double precision,
  de_t_yr_hi       double precision,
  p_decrease       double precision check (p_decrease is null or p_decrease between 0 and 1),
  mde_pct          double precision check (mde_pct is null or mde_pct between 0 and 100),
  n_before         integer not null check (n_before >= 0),
  n_after          integer not null check (n_after >= 0),
  controls         text,
  diag_ok          boolean,
  reason           text,
  evidence         text not null check (evidence in ('strong', 'weak', 'none')),
  size             text check (size is null or size in ('slight', 'moderate', 'severe')),
  colour           text not null check (colour in ('red', 'orange', 'yellow', 'green', 'grey')),
  plain_reading    text not null,
  provisional      boolean not null default false,
  restricted       boolean not null default true,
  primary key (publish_id, check_id),
  constraint check_results_effect_present check (call = 'insufficient_data' or effect_med is not null)
);
comment on table public.check_results is 'The before/after test for each check: measured change after the record with its 90% range, and the evidence, size and colour labels computed at publish time. A change that followed a date, never a cause.';

create table public.operator_reports (
  publish_id       text not null references public.publications (publish_id) on delete cascade,
  site_id          text not null,
  year             integer not null check (year between 2010 and 2100),
  source           text not null check (source in ('GHGRP', 'CARB-MRR')),
  reported_ch4_t   double precision not null check (reported_ch4_t >= 0),
  reported_co2e_t  double precision check (reported_co2e_t is null or reported_co2e_t >= 0),
  gwp_used         double precision,
  gwp_confirmed    boolean not null default false,
  facility_id      text not null,
  url              text not null,
  primary key (publish_id, site_id, year, source)
);
comment on table public.operator_reports is 'Annual methane the operator reported itself (EPA GHGRP). Published as t CO2e; the GWP used to convert back to methane is unconfirmed.';

create table public.population_context (
  publish_id  text not null references public.publications (publish_id) on delete cascade,
  site_id     text not null,
  radius_km   double precision not null check (radius_km > 0),
  residents   integer not null check (residents >= 0),
  label       text not null,
  primary key (publish_id, site_id, radius_km)
);
comment on table public.population_context is 'Residents within a radius of each site. Context only; never a model input and never a health claim.';

create table public.site_features (
  publish_id       text not null references public.publications (publish_id) on delete cascade,
  site_id          text not null,
  closed           boolean not null,
  area_km2         double precision check (area_km2 is null or area_km2 > 0),
  ghgrp_reporter   boolean not null,
  dist_neighbor_m  double precision check (dist_neighbor_m is null or dist_neighbor_m >= 0),
  primary key (publish_id, site_id)
);
comment on table public.site_features is 'Site traits shown as context on the site page.';

create table public.validation_results (
  publish_id   text not null references public.publications (publish_id) on delete cascade,
  report_id    text not null,
  gate         text not null,
  run_id       text,
  result       text not null check (result in ('pass', 'fail', 'dry-run')),
  metrics      jsonb not null default '{}'::jsonb,
  superseded   boolean not null default false,
  note         text,
  created_at   timestamptz,
  primary key (publish_id, report_id)
);
comment on table public.validation_results is 'Method checks (Gate 3 coverage, hold-out, placebo false-positive rate, power) read from reports/validation.';

create table public.update_log (
  publish_id    text not null references public.publications (publish_id) on delete cascade,
  item_order    integer not null,
  kind          text not null check (kind in (
                  'new-plumes', 'new-record', 'new-model-run', 'new-check-run', 'gate-result',
                  'outline-change', 'note')),
  site_id       text,
  event_date    date,
  count         integer check (count is null or count >= 0),
  text          text not null,
  data_through  date,
  primary key (publish_id, item_order)
);
comment on table public.update_log is 'What changed in each publication compared with the one before it.';

create table public.boundaries (
  boundary_id  text primary key,
  kind         text not null check (kind in ('county', 'air-district')),
  name         text not null,
  geom         extensions.geometry(MultiPolygon, 4326) not null,
  source       text,
  as_of        date
);
comment on table public.boundaries is 'Reference outlines for the map: counties and the Air District. Not tied to a publication.';

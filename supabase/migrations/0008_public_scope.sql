-- Public scope (ADR 0021).
--
-- A publication is public or not as a whole, but the project now holds sites that must stay on
-- the review copy until their operators and regulators have seen them. `mw publish build`
-- stamps every row from config/public_scope.json (an allowlist of regions and site tiers):
--   public_scope  the public website may show the row
--   site_public   plumes only: the public website may show which site the plume is tied to
--   region        the project region a site (by county) or a plume (by place) falls in
-- This migration adds the columns and makes every public path honour them: the row-level rules
-- for the publishable key, and the five functions behind the v_public_* views, which run with
-- their owner's rights and so must repeat the rule themselves.
--
-- A plume in an allowed region whose site is still under review stays on the public map as a
-- plain dot: the functions blank its site, its attribution, its distance and its pass id, and
-- the row-level rule keeps the full row away from the publishable key.
--
-- Everything defaults to "in scope", so rows loaded before this migration, and snapshots built
-- before it, show exactly as they did. One exception is spelled out below.

alter table public.sites
  add column region text,
  add column public_scope boolean not null default true;
alter table public.plumes
  add column region text,
  add column public_scope boolean not null default true,
  add column site_public boolean not null default true;
alter table public.neighbours add column public_scope boolean not null default true;
alter table public.passes add column public_scope boolean not null default true;
alter table public.site_estimates add column public_scope boolean not null default true;
alter table public.checks add column public_scope boolean not null default true;
alter table public.check_results add column public_scope boolean not null default true;
alter table public.operator_reports add column public_scope boolean not null default true;
alter table public.population_context add column public_scope boolean not null default true;
alter table public.site_features add column public_scope boolean not null default true;
alter table public.update_log add column public_scope boolean not null default true;

comment on column public.sites.region is
  'Project region the site''s county belongs to (config/project.yaml), for the public scope (ADR 0021).';
comment on column public.sites.public_scope is
  'The public website may show this site: its region and tier are on the allowlist (ADR 0021).';
comment on column public.plumes.region is
  'Project region whose box holds the plume; null outside every region (ADR 0021).';
comment on column public.plumes.public_scope is
  'The public website may show this plume: it lies in an allowed region (ADR 0021).';
comment on column public.plumes.site_public is
  'The public website may show which site this plume is tied to; false while that site is under review (ADR 0021).';

-- Rows loaded before the scope existed. Every site so far is a Bay Area pilot. Every plume so
-- far was pulled for the Bay Area box; a plume that lies just outside that box is in no region,
-- and by the rule above it leaves the public site (one NASA plume, east of the box).
update public.sites
   set region = 'bay-area'
 where county in ('Alameda', 'Contra Costa', 'Marin', 'Napa', 'San Francisco', 'San Mateo',
                  'Santa Clara', 'Solano', 'Sonoma');
update public.plumes
   set region = 'bay-area'
 where lon between -123.64 and -121.20 and lat between 36.89 and 38.87;
update public.plumes set public_scope = false where region is null;

-- ---- row-level rules for the publishable key ------------------------------------------------

alter policy sites_public_read on public.sites using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy neighbours_public_read on public.neighbours using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy plumes_public_read on public.plumes using (
  not restricted and public_scope and site_public
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy passes_public_read on public.passes using (
  not restricted and public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy site_estimates_public_read on public.site_estimates using (
  not restricted and public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy checks_public_read on public.checks using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy check_results_public_read on public.check_results using (
  not restricted and public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy operator_reports_public_read on public.operator_reports using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy population_context_public_read on public.population_context using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy site_features_public_read on public.site_features using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);
alter policy update_log_public_read on public.update_log using (
  public_scope
  and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
);

-- ---- read views: the new columns, added at the end ----------------------------------------

create or replace view public.v_sites
with (security_invoker = true) as
  select
    s.publish_id, s.site_id, s.name, s.city, s.county, s.operator, s.tier, s.status,
    s.swis_number, s.ghgrp_facility_id, s.polygon_source, s.provisional, s.area_km2,
    extensions.st_x(s.centroid) as lon,
    extensions.st_y(s.centroid) as lat,
    extensions.st_asgeojson(s.outline, 6)::jsonb as outline_geojson,
    s.region, s.public_scope
  from public.sites s;

create or replace view public.v_plumes
with (security_invoker = true) as
  select
    publish_id, plume_id, source, instrument, acquired_utc, lon, lat, q_kg_hr, q_sigma_kg_hr,
    site_id, attribution, distance_m, data_version, overpass_id, restricted, new_in_update,
    region, public_scope, site_public
  from public.plumes;

-- ---- functions behind the v_public_* views -------------------------------------------------

-- public_plumes gains a column, so it and its view are made again.
drop view public.v_public_plumes;
drop function public.public_plumes();

create function public.public_plumes()
returns table (
  publish_id text, plume_id text, source text, instrument text, acquired_utc timestamptz,
  lon double precision, lat double precision, q_kg_hr double precision,
  q_sigma_kg_hr double precision, site_id text, attribution text, distance_m double precision,
  data_version text, overpass_id text, restricted boolean, display_only boolean,
  new_in_update boolean, region text
)
language sql stable security definer set search_path = ''
as $$
  select
    p.publish_id,
    case when p.restricted
      then 'point-' || lpad(row_number() over (
        partition by p.publish_id, p.restricted order by p.acquired_utc, p.source, p.plume_id
      )::text, 5, '0')
      else p.plume_id end,
    p.source, p.instrument,
    case when p.restricted then date_trunc('day', p.acquired_utc) else p.acquired_utc end,
    p.lon, p.lat,
    case when p.restricted then null else p.q_kg_hr end,
    case when p.restricted then null else p.q_sigma_kg_hr end,
    case when p.site_public then p.site_id end,
    case when p.site_public then p.attribution else 'none' end,
    case when p.site_public then p.distance_m end,
    case when p.restricted then null else p.data_version end,
    case when p.restricted or not p.site_public then null else p.overpass_id end,
    p.restricted, p.display_only, p.new_in_update, p.region
  from public.plumes p
  join public.publications pub on pub.publish_id = p.publish_id
  where pub.visibility = 'public' and (not p.restricted or p.display_only) and p.public_scope
$$;

revoke all on function public.public_plumes() from public, anon, authenticated;
grant execute on function public.public_plumes() to anon;

create view public.v_public_plumes with (security_invoker = true) as
  select * from public.public_plumes();
comment on view public.v_public_plumes is
  'Plumes for the public site, in allowed regions only: open plumes in full, display-only plumes as dots without rate, id or data version (ADR 0017), and no site tie for a plume whose site is under review (ADR 0021).';
revoke all on public.v_public_plumes from anon, authenticated;
grant select on public.v_public_plumes to anon;

create or replace function public.public_pass_months()
returns table (
  publish_id text, site_id text, instrument text, restricted boolean, display_only boolean,
  month date, n_passes integer, n_usable integer, n_detected integer
)
language sql stable security definer set search_path = ''
as $$
  select
    p.publish_id, p.site_id, p.instrument, p.restricted, p.display_only,
    date_trunc('month', p.acquired_utc)::date,
    count(*)::integer,
    count(*) filter (where p.usable)::integer,
    count(*) filter (where p.usable and p.detected)::integer
  from public.passes p
  join public.publications pub on pub.publish_id = p.publish_id
  where pub.visibility = 'public' and (not p.restricted or p.display_only) and p.public_scope
  group by p.publish_id, p.site_id, p.instrument, p.restricted, p.display_only,
    date_trunc('month', p.acquired_utc)
$$;

create or replace function public.public_plume_days()
returns table (
  publish_id text, site_id text, usable_passes integer, plume_days integer,
  plume_days_per_usable_pass double precision, includes_restricted boolean,
  includes_display_only boolean
)
language sql stable security definer set search_path = ''
as $$
  select
    p.publish_id, p.site_id,
    count(*) filter (where p.usable)::integer,
    count(distinct p.acquired_utc::date) filter (where p.usable and p.detected)::integer,
    case
      when count(*) filter (where p.usable) = 0 then null
      else count(distinct p.acquired_utc::date) filter (where p.usable and p.detected)::double precision
           / count(*) filter (where p.usable)
    end,
    bool_or(p.restricted and not p.display_only),
    bool_or(p.display_only)
  from public.passes p
  join public.publications pub on pub.publish_id = p.publish_id
  where pub.visibility = 'public' and (not p.restricted or p.display_only) and p.public_scope
  group by p.publish_id, p.site_id
$$;

create or replace function public.public_site_estimates()
returns setof public.site_estimates
language sql stable security definer set search_path = ''
as $$
  select e.*
  from public.site_estimates e
  join public.publications pub on pub.publish_id = e.publish_id
  where pub.visibility = 'public' and (not e.restricted or e.display_only) and e.public_scope
$$;

create or replace function public.public_checks_with_results()
returns table (
  publish_id text, check_id text, site_id text, check_type text, repair_kind text,
  date_start date, date_end date, date_confidence text, description text, source_doc text,
  source_doc_title text, source_url text, source_page text, check_run_id text, call text,
  effect_med double precision, effect_lo double precision, effect_hi double precision,
  change_pct_med double precision, change_pct_lo double precision, change_pct_hi double precision,
  de_t_yr_med double precision, de_t_yr_lo double precision, de_t_yr_hi double precision,
  p_decrease double precision, mde_pct double precision, n_before integer, n_after integer,
  controls text, diag_ok boolean, reason text, evidence text, size text, colour text,
  plain_reading text, provisional boolean, restricted boolean, display_only boolean
)
language sql stable security definer set search_path = ''
as $$
  select
    c.publish_id, c.check_id, c.site_id, c.check_type, c.repair_kind, c.date_start, c.date_end,
    c.date_confidence, c.description, c.source_doc, c.source_doc_title, c.source_url, c.source_page,
    r.check_run_id, r.call, r.effect_med, r.effect_lo, r.effect_hi,
    r.change_pct_med, r.change_pct_lo, r.change_pct_hi,
    r.de_t_yr_med, r.de_t_yr_lo, r.de_t_yr_hi,
    r.p_decrease, r.mde_pct, r.n_before, r.n_after, r.controls, r.diag_ok, r.reason,
    r.evidence, r.size, r.colour, r.plain_reading, r.provisional, r.restricted, r.display_only
  from public.checks c
  join public.publications pub on pub.publish_id = c.publish_id
  left join public.check_results r
    on r.publish_id = c.publish_id and r.check_id = c.check_id
   and (not r.restricted or r.display_only) and r.public_scope
  where pub.visibility = 'public' and c.public_scope
$$;

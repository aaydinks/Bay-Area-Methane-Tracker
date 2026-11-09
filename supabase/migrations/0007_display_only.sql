-- Display-only data (ADR 0017).
--
-- Carbon Mapper agreed that figures built from its data may be shown on the website, but its data
-- may not be republished: no downloads, no data tables, no individual measured values. That is a
-- third level between hidden (restricted) and open. Rows from such a source keep restricted = true,
-- so the row-level rules in 0003 still keep them away from the publishable key, and they gain
-- display_only = true, set by `mw publish build`.
--
-- The public build reads five v_public_* views instead. Each is an ordinary view that runs with
-- the caller's rights over a function that runs with its owner's rights, so it can reach
-- display-only rows; the function returns rows of public publications only, and hands back only
-- what the site shows:
--   plumes        a display-only plume is a dot: place, day, site and attribution. Its rate, its
--                 uncertainty, its id and its data version are never returned.
--   pass months   counts per site, instrument and month, never the passes themselves.
--   plume days    counts per site.
--   estimates     the site figures with their ranges.
--   check results the result of each check.
-- The build keeps display-only rows out of every download (web/scripts/fetch-data.mjs), and
-- web/scripts/check-public-output.mjs fails a public build that lets one through.

alter table public.data_terms
  add column display_publishable boolean not null default false;
comment on column public.data_terms.display_publishable is
  'Figures built from this source may be shown on the website, but its data may not be downloaded or republished (ADR 0017).';

alter table public.plumes add column display_only boolean not null default false;
alter table public.passes add column display_only boolean not null default false;
alter table public.site_estimates add column display_only boolean not null default false;
alter table public.check_results add column display_only boolean not null default false;
comment on column public.plumes.display_only is
  'Restricted, but its source allows display: the public site shows it as a dot without its rate (ADR 0017).';
comment on column public.passes.display_only is
  'Restricted, but its source allows display: the public site shows it only inside monthly and per-site counts (ADR 0017).';
comment on column public.site_estimates.display_only is
  'Restricted, but every restricted source behind it allows display: shown on the public site, left out of downloads (ADR 0017).';
comment on column public.check_results.display_only is
  'Restricted, but every restricted source behind it allows display: shown on the public site, left out of downloads (ADR 0017).';

-- ---- functions (owner's rights, public publications only) -------------------------------

create function public.public_plumes()
returns table (
  publish_id text, plume_id text, source text, instrument text, acquired_utc timestamptz,
  lon double precision, lat double precision, q_kg_hr double precision,
  q_sigma_kg_hr double precision, site_id text, attribution text, distance_m double precision,
  data_version text, overpass_id text, restricted boolean, display_only boolean,
  new_in_update boolean
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
    p.site_id, p.attribution, p.distance_m,
    case when p.restricted then null else p.data_version end,
    case when p.restricted then null else p.overpass_id end,
    p.restricted, p.display_only, p.new_in_update
  from public.plumes p
  join public.publications pub on pub.publish_id = p.publish_id
  where pub.visibility = 'public' and (not p.restricted or p.display_only)
$$;

create function public.public_pass_months()
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
  where pub.visibility = 'public' and (not p.restricted or p.display_only)
  group by p.publish_id, p.site_id, p.instrument, p.restricted, p.display_only,
    date_trunc('month', p.acquired_utc)
$$;

create function public.public_plume_days()
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
  where pub.visibility = 'public' and (not p.restricted or p.display_only)
  group by p.publish_id, p.site_id
$$;

create function public.public_site_estimates()
returns setof public.site_estimates
language sql stable security definer set search_path = ''
as $$
  select e.*
  from public.site_estimates e
  join public.publications pub on pub.publish_id = e.publish_id
  where pub.visibility = 'public' and (not e.restricted or e.display_only)
$$;

create function public.public_checks_with_results()
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
   and (not r.restricted or r.display_only)
  where pub.visibility = 'public'
$$;

revoke all on function
  public.public_plumes(), public.public_pass_months(), public.public_plume_days(),
  public.public_site_estimates(), public.public_checks_with_results()
from public, anon, authenticated;
grant execute on function
  public.public_plumes(), public.public_pass_months(), public.public_plume_days(),
  public.public_site_estimates(), public.public_checks_with_results()
to anon;

-- ---- views (caller's rights, like every other view) -------------------------------------

create view public.v_public_plumes with (security_invoker = true) as
  select * from public.public_plumes();
comment on view public.v_public_plumes is
  'Plumes for the public site: open plumes in full, display-only plumes as dots without rate, id or data version (ADR 0017).';

create view public.v_public_pass_months with (security_invoker = true) as
  select * from public.public_pass_months();
comment on view public.v_public_pass_months is
  'Passes per site, instrument and month for the public site, counting display-only passes (ADR 0017).';

create view public.v_public_plume_days with (security_invoker = true) as
  select * from public.public_plume_days();
comment on view public.v_public_plume_days is
  'Plume days per site for the public site, counting display-only passes (ADR 0017).';

create view public.v_public_site_estimates with (security_invoker = true) as
  select * from public.public_site_estimates();
comment on view public.v_public_site_estimates is
  'Site estimates for the public site, including display-only ones, which the build keeps out of downloads (ADR 0017).';

create view public.v_public_checks_with_results with (security_invoker = true) as
  select * from public.public_checks_with_results();
comment on view public.v_public_checks_with_results is
  'Checks with their results for the public site, including display-only results, which the build keeps out of downloads (ADR 0017).';

revoke all on
  public.v_public_plumes, public.v_public_pass_months, public.v_public_plume_days,
  public.v_public_site_estimates, public.v_public_checks_with_results
from anon, authenticated;
grant select on
  public.v_public_plumes, public.v_public_pass_months, public.v_public_plume_days,
  public.v_public_site_estimates, public.v_public_checks_with_results
to anon;

-- Read views for the website build.
--
-- Every view runs with the caller's own rights (security_invoker), so the row-level rules on the
-- tables apply to it too: the publishable key sees public, unrestricted rows and nothing else.
-- Geometry is handed over as GeoJSON or plain longitude and latitude so no client needs PostGIS.
-- The build chooses the publication it wants; the views do not pick one for it, except the two
-- "current" views that name the newest one a caller may see.

create view public.v_current_publication
with (security_invoker = true) as
  select *
  from public.publications
  where visibility = 'public'
  order by created_at desc
  limit 1;
comment on view public.v_current_publication is 'The newest public publication.';

create view public.v_current_review_publication
with (security_invoker = true) as
  select *
  from public.publications
  where visibility in ('review', 'public')
  order by created_at desc
  limit 1;
comment on view public.v_current_review_publication is 'The newest publication the caller may see at review level or above. For the publishable key this is the same as v_current_publication.';

create view public.v_sites
with (security_invoker = true) as
  select
    s.publish_id, s.site_id, s.name, s.city, s.county, s.operator, s.tier, s.status,
    s.swis_number, s.ghgrp_facility_id, s.polygon_source, s.provisional, s.area_km2,
    extensions.st_x(s.centroid) as lon,
    extensions.st_y(s.centroid) as lat,
    extensions.st_asgeojson(s.outline, 6)::jsonb as outline_geojson
  from public.sites s;

create view public.v_neighbours
with (security_invoker = true) as
  select
    n.publish_id, n.neighbour_id, n.name, n.kind, n.nearest_site_id, n.distance_m, n.source,
    extensions.st_asgeojson(n.geom, 6)::jsonb as geojson
  from public.neighbours n;

create view public.v_plumes
with (security_invoker = true) as
  select
    publish_id, plume_id, source, instrument, acquired_utc, lon, lat, q_kg_hr, q_sigma_kg_hr,
    site_id, attribution, distance_m, data_version, overpass_id, restricted, new_in_update
  from public.plumes;

create view public.v_pass_months
with (security_invoker = true) as
  select
    publish_id, site_id, instrument, restricted,
    date_trunc('month', acquired_utc)::date as month,
    count(*)::integer as n_passes,
    count(*) filter (where usable)::integer as n_usable,
    count(*) filter (where usable and detected)::integer as n_detected
  from public.passes
  group by publish_id, site_id, instrument, restricted, date_trunc('month', acquired_utc);
comment on view public.v_pass_months is 'Passes per site, instrument and month. Plume counts must be read against these, because a site that is flown more often shows more plumes.';

create view public.v_plume_days
with (security_invoker = true) as
  select
    publish_id, site_id,
    count(*) filter (where usable)::integer as usable_passes,
    count(distinct acquired_utc::date) filter (where usable and detected)::integer as plume_days,
    case
      when count(*) filter (where usable) = 0 then null
      else count(distinct acquired_utc::date) filter (where usable and detected)::double precision
           / count(*) filter (where usable)
    end as plume_days_per_usable_pass,
    bool_or(restricted) as includes_restricted
  from public.passes
  group by publish_id, site_id;
comment on view public.v_plume_days is 'Plume days and plume days per usable pass, per site, so the heat map is not read as emissions.';

create view public.v_checks_with_results
with (security_invoker = true) as
  select
    c.publish_id, c.check_id, c.site_id, c.check_type, c.repair_kind, c.date_start, c.date_end,
    c.date_confidence, c.description, c.source_doc, c.source_doc_title, c.source_url, c.source_page,
    r.check_run_id, r.call, r.effect_med, r.effect_lo, r.effect_hi,
    r.change_pct_med, r.change_pct_lo, r.change_pct_hi,
    r.de_t_yr_med, r.de_t_yr_lo, r.de_t_yr_hi,
    r.p_decrease, r.mde_pct, r.n_before, r.n_after, r.controls, r.diag_ok, r.reason,
    r.evidence, r.size, r.colour, r.plain_reading, r.provisional, r.restricted
  from public.checks c
  left join public.check_results r
    on r.publish_id = c.publish_id and r.check_id = c.check_id;
comment on view public.v_checks_with_results is 'Each dated check with its result when one exists. A check without a result is shown as not yet tested.';

create view public.v_operator_comparison
with (security_invoker = true) as
  select
    e.publish_id, e.site_id, e.period, e.model_run_id,
    e.e_t_yr_med, e.e_t_yr_lo, e.e_t_yr_hi, e.status, e.provisional, e.restricted,
    o.year as reported_year, o.source as reported_source, o.reported_ch4_t, o.reported_co2e_t,
    o.gwp_used, o.gwp_confirmed, o.url as reported_url
  from public.site_estimates e
  left join public.operator_reports o
    on o.publish_id = e.publish_id and o.site_id = e.site_id;
comment on view public.v_operator_comparison is 'Satellite estimate beside the operator-reported figure, year by year. The GWP used to convert the reported figure is unconfirmed.';

create view public.v_boundaries
with (security_invoker = true) as
  select
    boundary_id, kind, name, source, as_of,
    extensions.st_asgeojson(geom, 5)::jsonb as geojson
  from public.boundaries;

-- The grants in 0003 covered the tables that existed then. Views are relations too and need
-- their own: the publishable key may read them, nobody writes through them.
revoke all on
  public.v_current_publication, public.v_current_review_publication, public.v_sites,
  public.v_neighbours, public.v_plumes, public.v_pass_months, public.v_plume_days,
  public.v_checks_with_results, public.v_operator_comparison, public.v_boundaries
from anon, authenticated;
grant select on
  public.v_current_publication, public.v_current_review_publication, public.v_sites,
  public.v_neighbours, public.v_plumes, public.v_pass_months, public.v_plume_days,
  public.v_checks_with_results, public.v_operator_comparison, public.v_boundaries
to anon;

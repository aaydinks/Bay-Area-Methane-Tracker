-- Site identifiers (ADR 0018).
--
-- Each site now records which air district it sits in and its facility number at that
-- district. The district is read from CARB's 2004 outlines until a person has checked it, so
-- it carries a flag saying whether it is confirmed. `swis_number` and `region` are already
-- here (0002, 0008).
--
-- Additive only: three columns on `sites`, and `v_sites` shows them at the end. Rows loaded
-- before this migration have no district and read as unconfirmed.

alter table public.sites
  add column air_district text,
  add column air_district_confirmed boolean not null default false,
  add column district_facility_id text;

comment on column public.sites.air_district is
  'Air district the site sits in, by CARB''s district name. From CARB''s 2004 outlines unless air_district_confirmed.';
comment on column public.sites.air_district_confirmed is
  'True once a person has checked the air district against the district itself (ADR 0018).';
comment on column public.sites.district_facility_id is
  'The site''s facility number at its air district, from permits; null until sourced.';

create or replace view public.v_sites
with (security_invoker = true) as
  select
    s.publish_id, s.site_id, s.name, s.city, s.county, s.operator, s.tier, s.status,
    s.swis_number, s.ghgrp_facility_id, s.polygon_source, s.provisional, s.area_km2,
    extensions.st_x(s.centroid) as lon,
    extensions.st_y(s.centroid) as lat,
    extensions.st_asgeojson(s.outline, 6)::jsonb as outline_geojson,
    s.region, s.public_scope,
    s.air_district, s.air_district_confirmed, s.district_facility_id
  from public.sites s;

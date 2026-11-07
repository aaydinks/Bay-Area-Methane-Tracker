-- Where a pass's cloud-free share comes from (ADR 0014).
--
-- Sentinel-2 passes now take Sen2Cor's clear share over each site as valid_frac instead of the
-- cloud figure for the whole tile. The tile figure is kept beside it so the two can be compared,
-- and valid_frac_source says which one valid_frac holds. Both columns are nullable: publications
-- built before the change carry neither, and only Sentinel-2 passes have a tile figure.
--
-- No view changes: v_pass_months and v_plume_days only count passes, and no view lists the
-- pass columns one by one. The table-wide select grant in 0003 covers the new columns.

alter table public.passes
  add column valid_frac_tile double precision
    constraint passes_valid_frac_tile_range check (valid_frac_tile between 0 and 1);

alter table public.passes
  add column valid_frac_source text
    constraint passes_valid_frac_source_check
    check (valid_frac_source in ('site-sen2cor', 'tile', 'scene'));

comment on column public.passes.valid_frac_tile is
  'Sentinel-2 only: the cloud-free share of the whole tile (1 - eo:cloud_cover/100), kept for comparison with valid_frac. Null for other instruments and for publications built before ADR 0014.';
comment on column public.passes.valid_frac_source is
  'What valid_frac holds: site-sen2cor (Sen2Cor''s clear share over the site), tile (a Sentinel-2 pass with no Sen2Cor share, so the tile figure) or scene (other instruments: EMIT''s scene figure, and 1 for Carbon Mapper scenes, which carry no cloud mask). Null for publications built before ADR 0014.';

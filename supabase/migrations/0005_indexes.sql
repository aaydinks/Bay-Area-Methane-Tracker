-- Indexes for the build's queries: by publication and site, by time, and spatial.

create index publications_visibility_created_idx on public.publications (visibility, created_at desc);

create index sites_outline_gix        on public.sites using gist (outline);
create index neighbours_geom_gix      on public.neighbours using gist (geom);
create index neighbours_site_idx      on public.neighbours (publish_id, nearest_site_id);

create index plumes_geom_gix          on public.plumes using gist (geom);
create index plumes_site_idx          on public.plumes (publish_id, site_id);
create index plumes_source_time_idx   on public.plumes (publish_id, source, acquired_utc);
create index plumes_restricted_idx    on public.plumes (publish_id, restricted);

create index passes_site_time_idx     on public.passes (publish_id, site_id, instrument, acquired_utc);
create index passes_restricted_idx    on public.passes (publish_id, restricted);

create index site_estimates_site_idx  on public.site_estimates (publish_id, site_id);
create index checks_site_idx          on public.checks (publish_id, site_id, date_start);
create index check_results_site_idx   on public.check_results (publish_id, site_id);
create index operator_reports_site_idx on public.operator_reports (publish_id, site_id, year);
create index population_site_idx      on public.population_context (publish_id, site_id);
create index validation_gate_idx      on public.validation_results (publish_id, gate);
create index update_log_site_idx      on public.update_log (publish_id, site_id);
create index boundaries_geom_gix      on public.boundaries using gist (geom);

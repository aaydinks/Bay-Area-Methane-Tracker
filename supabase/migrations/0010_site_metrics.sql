-- Measures beside the methane estimate (ADR 0019).
--
-- Everything a site page shows that is not a methane estimate goes in one long table: the
-- gases an operator reports to EPA now, and later plume counts for other gases, site
-- operations and context such as nearby air monitors. The methane tables get no gas column.
--
--   site_metrics      one row per site, measure, period and source: a number or a text value
--                     with its unit, whose statement it is (`kind`), and the same restricted,
--                     display_only and public_scope flags the other tables carry
--   metric_catalogue  the label, unit, kind, source and caveat of each measure, as the
--                     publication was built with them (config/metrics.yaml)
--
-- Additive only: two new tables, their row-level rules and grants. No existing table, view or
-- function changes, and a publication loaded before this migration simply has no rows here.

create table public.metric_catalogue (
  publish_id  text not null references public.publications (publish_id) on delete cascade,
  metric_id   text not null check (length(metric_id) > 0),
  label       text not null check (length(label) > 0),
  unit        text not null check (length(unit) > 0),
  kind        text not null check (kind in ('reported', 'observed', 'context')),
  source      text not null check (length(source) > 0),
  caveat      text,
  sort_order  integer not null check (sort_order >= 1),
  primary key (publish_id, metric_id),
  unique (publish_id, sort_order)
);
comment on table public.metric_catalogue is 'The measures a publication can show beside the methane estimate, with the label and caveat each was published with (ADR 0019).';
comment on column public.metric_catalogue.kind is
  'reported: an operator or agency says so. observed: the project counted it in public data. context: describes the surroundings, never the landfill (ADR 0020).';

create table public.site_metrics (
  publish_id    text not null references public.publications (publish_id) on delete cascade,
  site_id       text not null,
  metric_id     text not null,
  period        text not null check (length(period) > 0),
  source        text not null check (length(source) > 0),
  value         double precision,
  value_text    text,
  unit          text not null check (length(unit) > 0),
  kind          text not null check (kind in ('reported', 'observed', 'context')),
  confirmed     boolean not null default false,
  source_id     text,
  url           text,
  restricted    boolean not null default true,
  display_only  boolean not null default false,
  public_scope  boolean not null default true,
  primary key (publish_id, site_id, metric_id, period, source),
  constraint site_metrics_value_present check (value is not null or value_text is not null),
  constraint site_metrics_in_catalogue foreign key (publish_id, metric_id)
    references public.metric_catalogue (publish_id, metric_id) on delete cascade
);
comment on table public.site_metrics is 'Measures beside the methane estimate, one row per site, measure, period and source (ADR 0019). Figures are in the unit their source publishes; a missing row means not reported, never zero.';
comment on column public.site_metrics.period is
  'The period the figure covers, as text: a year such as 2023 for annual figures.';
comment on column public.site_metrics.source is
  'The source of the figure, a key of data_terms.source.';
comment on column public.site_metrics.source_id is
  'The site''s identifier at the source, such as its EPA facility number.';
comment on column public.site_metrics.restricted is
  'True unless the source''s terms allow figures built from it to be published (data_terms).';
comment on column public.site_metrics.public_scope is
  'The public website may show this row: its site is on the allowlist (ADR 0021).';

-- ---- row-level rules -------------------------------------------------------------------------
-- The publishable key reads rows of public publications only, never a restricted row and never
-- a row about a site that is still under review. A display-only row stays hidden here: no
-- measure needs the reduced public form yet, and the step that adds one decides how to serve it.

alter table public.metric_catalogue enable row level security;
alter table public.site_metrics enable row level security;

revoke all on public.metric_catalogue, public.site_metrics from anon, authenticated;
grant select on public.metric_catalogue, public.site_metrics to anon;

create policy metric_catalogue_public_read on public.metric_catalogue
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy site_metrics_public_read on public.site_metrics
  for select to anon using (
    not restricted and public_scope
    and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

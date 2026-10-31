-- Row-level security.
--
-- The publishable (anon) key may read rows of public publications only, and never a restricted
-- row. It may not write anything. Signed-in users do not exist on this project, so the
-- authenticated role gets nothing. The secret key bypasses these rules by design: it is used
-- only by the publishing command and by the protected review build, at build time.

alter table public.publications      enable row level security;
alter table public.runs              enable row level security;
alter table public.data_terms        enable row level security;
alter table public.sites             enable row level security;
alter table public.neighbours        enable row level security;
alter table public.plumes            enable row level security;
alter table public.passes            enable row level security;
alter table public.site_estimates    enable row level security;
alter table public.checks            enable row level security;
alter table public.check_results     enable row level security;
alter table public.operator_reports  enable row level security;
alter table public.population_context enable row level security;
alter table public.site_features     enable row level security;
alter table public.validation_results enable row level security;
alter table public.update_log        enable row level security;
alter table public.boundaries        enable row level security;

-- Supabase grants the API roles broad privileges on new tables by default. Take writes away
-- and give the publishable key read access only; policies below decide which rows.
revoke all on all tables in schema public from anon, authenticated;
grant select on all tables in schema public to anon;

create policy publications_public_read on public.publications
  for select to anon using (visibility = 'public');

create policy runs_public_read on public.runs
  for select to anon using (
    run_id in (
      select p.model_run_id from public.publications p where p.visibility = 'public'
      union select p.check_run_id from public.publications p where p.visibility = 'public'
      union select p.refresh_id from public.publications p where p.visibility = 'public'
    )
  );

create policy data_terms_public_read on public.data_terms
  for select to anon using (true);

create policy boundaries_public_read on public.boundaries
  for select to anon using (true);

create policy sites_public_read on public.sites
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy neighbours_public_read on public.neighbours
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy plumes_public_read on public.plumes
  for select to anon using (
    not restricted
    and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy passes_public_read on public.passes
  for select to anon using (
    not restricted
    and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy site_estimates_public_read on public.site_estimates
  for select to anon using (
    not restricted
    and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy checks_public_read on public.checks
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy check_results_public_read on public.check_results
  for select to anon using (
    not restricted
    and publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy operator_reports_public_read on public.operator_reports
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy population_context_public_read on public.population_context
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy site_features_public_read on public.site_features
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy validation_results_public_read on public.validation_results
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

create policy update_log_public_read on public.update_log
  for select to anon using (
    publish_id in (select p.publish_id from public.publications p where p.visibility = 'public')
  );

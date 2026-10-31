-- Extensions and roles the publishing database needs.
--
-- PostGIS holds site outlines, plume points and county outlines. Supabase keeps extensions in
-- the "extensions" schema; the PostGIS container used in CI has no such schema, so it is created
-- here first. The anon and authenticated roles exist on Supabase already and are created only
-- where they are missing (CI), so the same file runs in both places.

create schema if not exists extensions;
create extension if not exists postgis with schema extensions;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end
$$;

grant usage on schema public to anon;
grant usage on schema extensions to anon;

-- Supabase installs an event-trigger helper that switches row-level security on for every new
-- table in "public". That is wanted, but the function itself must not be callable through the
-- API (the security advisor flags it when it is).
do $$
begin
  if exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'rls_auto_enable'
  ) then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end
$$;

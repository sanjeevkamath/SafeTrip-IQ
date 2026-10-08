-- Phase 0: targeted containment based on the owner's live catalog audit.
-- Run in the Supabase SQL Editor as the database administrator.
-- Does not change table data or SELECT access.
-- PUBLIC below is the all-roles group, not the public schema.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

DROP POLICY IF EXISTS "Allow public update for countries"
    ON public.countries;

REVOKE UPDATE ON TABLE public.countries
    FROM PUBLIC, anon, authenticated;

COMMIT;

-- Expected: no UPDATE/ALL policies from the supplied baseline remain.
SELECT policyname, roles, cmd, qual, with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename = 'countries'
ORDER BY policyname;

-- Expected: SELECT=true, UPDATE=false for each role.
-- Column grants, inherited roles, views and functions require the wider audit.
SELECT role_name,
       has_table_privilege(role_name, 'public.countries', 'SELECT') AS can_select,
       has_table_privilege(role_name, 'public.countries', 'UPDATE') AS can_update,
       has_any_column_privilege(role_name, 'public.countries', 'UPDATE')
           AS can_update_any_column
FROM (VALUES ('anon'), ('authenticated')) AS roles(role_name);

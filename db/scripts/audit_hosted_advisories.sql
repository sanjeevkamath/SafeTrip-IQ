-- Run in Supabase SQL Editor. Read-only: no credentials or application text.
-- Share the single JSON result; do not share connection strings or API keys.
BEGIN READ ONLY;
SELECT jsonb_build_object(
  'server_version', current_setting('server_version'),
  'schemas', (SELECT jsonb_agg(nspname ORDER BY nspname) FROM pg_namespace
              WHERE nspname IN ('public','advisory')),
  'relations', (SELECT jsonb_agg(jsonb_build_object(
      'schema', n.nspname, 'name', c.relname, 'kind', c.relkind,
      'owner', pg_get_userbyid(c.relowner), 'rls', c.relrowsecurity,
      'force_rls', c.relforcerowsecurity, 'options', c.reloptions,
      'acl', c.relacl::text) ORDER BY n.nspname,c.relname)
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname IN ('public','advisory') AND c.relkind IN ('r','p','v','m')),
  'columns', (SELECT jsonb_agg(jsonb_build_object(
      'schema',n.nspname,'table',c.relname,'column',a.attname,
      'type',format_type(a.atttypid,a.atttypmod),'required',a.attnotnull,
      'column_acl',a.attacl::text) ORDER BY n.nspname,c.relname,a.attnum)
    FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname IN ('public','advisory') AND c.relkind IN ('r','p','v','m')
      AND a.attnum>0 AND NOT a.attisdropped),
  'policies', (SELECT jsonb_agg(to_jsonb(p)) FROM pg_policies p
              WHERE schemaname IN ('public','advisory')),
  'roles', (SELECT jsonb_agg(jsonb_build_object('role',rolname,
      'login',rolcanlogin,'superuser',rolsuper,'bypass_rls',rolbypassrls,
      'create_role',rolcreaterole,'create_db',rolcreatedb)) FROM pg_roles
    WHERE rolname IN ('anon','authenticated','service_role',
                     'safetrip_reader','safetrip_writer','safetrip_migrator')),
  'memberships', (SELECT jsonb_agg(jsonb_build_object(
      'member',member.rolname,'granted_role',parent.rolname))
    FROM pg_auth_members m JOIN pg_roles member ON member.oid=m.member
    JOIN pg_roles parent ON parent.oid=m.roleid
    WHERE member.rolname IN ('anon','authenticated','service_role',
                            'safetrip_reader','safetrip_writer','safetrip_migrator')),
  'constraints', (SELECT jsonb_agg(jsonb_build_object('schema',n.nspname,
      'table',c.relname,'name',k.conname,'definition',pg_get_constraintdef(k.oid)))
    FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname IN ('public','advisory')),
  'functions', (SELECT jsonb_agg(jsonb_build_object('schema',n.nspname,
      'name',p.proname,'arguments',pg_get_function_identity_arguments(p.oid),
      'security_definer',p.prosecdef,'acl',p.proacl::text))
    FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname IN ('public','advisory','graphql_public')),
  'country_catalogue', (SELECT jsonb_build_object('count',count(*),
      'iso3_codes',jsonb_agg(iso3 ORDER BY iso3)) FROM public.countries),
  'alembic_table_present', to_regclass('public.alembic_version') IS NOT NULL
) AS audit;
COMMIT;

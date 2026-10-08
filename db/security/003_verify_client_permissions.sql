-- Read-only post-deployment check. All 18 rows should say expected_access=true.
WITH permissions AS (
    SELECT c.relname AS table_name, r.role_name,
           c.relrowsecurity AS rls_enabled,
           has_table_privilege(r.role_name,c.oid,'SELECT') AS can_select,
           has_table_privilege(r.role_name,c.oid,'INSERT') AS can_insert,
           has_table_privilege(r.role_name,c.oid,'UPDATE') AS can_update,
           has_table_privilege(r.role_name,c.oid,'DELETE') AS can_delete,
           has_table_privilege(r.role_name,c.oid,'TRUNCATE') AS can_truncate,
           has_table_privilege(r.role_name,c.oid,'REFERENCES') AS can_reference,
           has_table_privilege(r.role_name,c.oid,'TRIGGER') AS can_trigger,
           has_table_privilege(r.role_name,c.oid,'MAINTAIN') AS can_maintain,
           has_any_column_privilege(r.role_name,c.oid,'INSERT') AS column_insert,
           has_any_column_privilege(r.role_name,c.oid,'UPDATE') AS column_update
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    CROSS JOIN (VALUES ('anon'),('authenticated'),('service_role')) r(role_name)
    WHERE n.nspname='public' AND c.relkind IN ('r','p')
      AND c.relname IN ('countries','culture','scores','bert_scores','clustering','travel_advisories')
)
SELECT table_name, role_name, rls_enabled, can_select,
       can_insert, can_update, can_delete, can_truncate,
       rls_enabled AND CASE WHEN role_name='service_role'
           THEN can_select AND can_insert AND can_update AND can_delete
           ELSE NOT (can_insert OR can_update OR can_delete OR can_truncate
                     OR can_reference OR can_trigger OR can_maintain
                     OR column_insert OR column_update)
                AND can_select = CASE WHEN role_name='anon'
                    THEN table_name IN ('countries','culture','scores')
                    ELSE table_name='countries' END
       END AS expected_access
FROM permissions
ORDER BY table_name, role_name;

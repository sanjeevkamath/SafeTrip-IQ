-- PostgreSQL 17; reviewed against the backed-up SafeTrip public schema.
-- Does not change rows or service_role grants. Apply only after schema backup.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

-- No table or column-specific public write privileges are needed by this app.
-- The live audit confirmed no column ACLs or client role memberships.
REVOKE ALL PRIVILEGES ON TABLE
    public.bert_scores, public.clustering, public.countries,
    public.culture, public.scores, public.travel_advisories
FROM PUBLIC, anon, authenticated;

-- Preserve the actual read paths present in the audited policies.
GRANT SELECT ON TABLE public.countries, public.culture, public.scores TO anon;
GRANT SELECT ON TABLE public.countries TO authenticated;

ALTER TABLE public.bert_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clustering ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.countries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.culture ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.travel_advisories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public update for countries" ON public.countries;

-- Prevent postgres-created future tables/sequences in public from inheriting
-- the same broad client access. Grant each new public read path explicitly.
-- This affects future objects, not existing objects, and is creator-specific.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated;

COMMIT;

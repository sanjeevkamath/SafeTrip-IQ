-- DEVELOPMENT ONLY. Run as the Compose admin before Alembic.
-- Fixed local passwords make fresh clones reproducible; never use on a hosted DB.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'safetrip_migrator') THEN
        CREATE ROLE safetrip_migrator LOGIN PASSWORD 'migrator_local_only';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'safetrip_reader') THEN
        CREATE ROLE safetrip_reader LOGIN PASSWORD 'reader_local_only';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'safetrip_writer') THEN
        CREATE ROLE safetrip_writer LOGIN PASSWORD 'writer_local_only';
    END IF;
END $$;
ALTER ROLE safetrip_migrator NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE safetrip_reader NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE safetrip_writer NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE safetrip FROM PUBLIC;
GRANT CONNECT ON DATABASE safetrip TO safetrip_migrator, safetrip_reader, safetrip_writer;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO safetrip_migrator;
GRANT USAGE ON SCHEMA public TO safetrip_reader, safetrip_writer;
-- New tables/functions receive no automatic application privileges.
ALTER DEFAULT PRIVILEGES FOR ROLE safetrip_migrator IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE safetrip_migrator
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
COMMIT;

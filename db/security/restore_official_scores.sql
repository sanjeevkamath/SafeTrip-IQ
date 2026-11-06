-- OWNER-ONLY INCIDENT TOOL. See docs/operations.md before use.
-- Disable automated writes first. Replace the UUID, rehearse with ROLLBACK,
-- inspect counts, then deliberately change the final ROLLBACK to COMMIT.
-- Retains all advisory/model/history records and records the restoration event.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $restore$
DECLARE
    incident uuid := 'REPLACE_WITH_INCIDENT_RUN_UUID';
    event_id uuid := gen_random_uuid();
    receipt public.pipeline_runs%ROWTYPE;
    restored integer;
    removed integer;
BEGIN
    IF current_user NOT IN ('postgres','safetrip_admin') THEN
        RAISE EXCEPTION 'Restoration requires the reviewed owner connection';
    END IF;
    IF NOT pg_try_advisory_xact_lock(73481002) OR NOT pg_try_advisory_xact_lock(73481001) THEN
        RAISE EXCEPTION 'A refresh/publication is active; restoration aborted';
    END IF;
    LOCK TABLE public.scores IN EXCLUSIVE MODE;
    SELECT * INTO STRICT receipt FROM public.pipeline_runs WHERE run_id=incident FOR UPDATE;
    IF receipt.command <> 'publish-official-scores' OR receipt.status <> 'succeeded'
        OR jsonb_typeof(receipt.input_payload->'published_scores') IS DISTINCT FROM 'array'
        OR receipt.published_rows <= 0 THEN
        RAISE EXCEPTION 'Expected a successful official publication with its prior snapshot';
    END IF;
    IF (SELECT count(*) FROM public.official_score_history WHERE run_id=incident) <> receipt.published_rows
        OR (SELECT count(*) FROM public.scores WHERE score_run_id=incident) <> receipt.published_rows
        OR EXISTS (SELECT 1 FROM public.official_score_history h LEFT JOIN public.scores s USING(iso3)
            WHERE h.run_id=incident AND (s.score_run_id IS DISTINCT FROM incident
                OR s.safe_trip_score IS DISTINCT FROM h.safe_trip_score
                OR s.scoring_version IS DISTINCT FROM h.scoring_version
                OR s.official_us_level IS DISTINCT FROM (h.inputs->>'official_us_level')::smallint
                OR s.official_us_component IS DISTINCT FROM (h.inputs->>'official_us_component')::real
                OR s.clustering_component IS DISTINCT FROM (h.inputs->>'clustering_component')::real)) THEN
        RAISE EXCEPTION 'Current rows no longer match this publication; refusing stale restoration';
    END IF;
    -- Do not erase a later correction to a model input, even by the owner.
    IF EXISTS (SELECT 1 FROM public.scores s
        LEFT JOIN jsonb_array_elements(receipt.input_payload->'published_scores') p
            ON p->>'iso3'=s.iso3
        WHERE s.score_run_id=incident AND (
            s.bert_score IS DISTINCT FROM (p->>'bert_score')::integer OR
            s.clustering_score IS DISTINCT FROM (p->>'clustering_score')::integer)) THEN
        RAISE EXCEPTION 'Historical model inputs differ; investigate instead of restoring';
    END IF;
    UPDATE public.scores s SET
        safe_trip_score=(p->>'safe_trip_score')::real,
        official_us_level=(p->>'official_us_level')::smallint,
        official_us_component=(p->>'official_us_component')::real,
        clustering_component=(p->>'clustering_component')::real,
        scoring_version=p->>'scoring_version', score_run_id=(p->>'score_run_id')::uuid,
        score_published_at=(p->>'score_published_at')::timestamptz
    FROM jsonb_array_elements(receipt.input_payload->'published_scores') p
    WHERE s.iso3=p->>'iso3' AND s.score_run_id=incident;
    GET DIAGNOSTICS restored=ROW_COUNT;
    -- Remove only score rows first created by this publication, never countries.
    DELETE FROM public.scores s WHERE s.score_run_id=incident AND NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(receipt.input_payload->'published_scores') p WHERE p->>'iso3'=s.iso3);
    GET DIAGNOSTICS removed=ROW_COUNT;
    INSERT INTO public.pipeline_runs(run_id,command,status,started_at,finished_at,metadata,published_rows)
        VALUES(event_id,'restore-official-scores','succeeded',now(),now(),
            jsonb_build_object('restored_publication',incident,'restored_existing_rows',restored,
                'removed_new_score_rows',removed),restored);
    RAISE NOTICE 'Restored % prior score rows; removed % newly inserted score rows. Restore event: %',restored,removed,event_id;
END $restore$;
ROLLBACK;

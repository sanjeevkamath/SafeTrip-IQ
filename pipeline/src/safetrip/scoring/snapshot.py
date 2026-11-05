"""Shared explicit read projection for preview and locked publication."""
import hashlib
import json

COUNTRIES_SQL='SELECT iso3,name FROM public.countries ORDER BY iso3'
PUBLISHED_SQL="""SELECT iso3,safe_trip_score,bert_score,clustering_score,
    to_jsonb(s)->>'scoring_version' AS scoring_version,
    to_jsonb(s)->>'official_us_level' AS official_us_level,
    to_jsonb(s)->>'official_us_component' AS official_us_component,
    to_jsonb(s)->>'clustering_component' AS clustering_component,
    to_jsonb(s)->>'score_run_id' AS score_run_id,
    to_jsonb(s)->>'score_published_at' AS score_published_at
    FROM public.scores s ORDER BY iso3"""
ADVISORIES_SQL="""SELECT iso3,document_id,version_id,source,source_url,
    to_char(source_public_updated_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS source_public_updated_at,
    to_char(fetched_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS fetched_at,
    us_level,coverage_scope,region_label FROM public.advisory_summaries
    WHERE source='us_state' ORDER BY iso3,document_id"""


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def calculate(snapshot):
    from .official import preview_scores
    return preview_scores(snapshot['countries'],{r['iso3'].strip():r for r in snapshot['published_scores']},
                          snapshot['official_us_advisories'],'exclude')

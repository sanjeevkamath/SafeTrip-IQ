import 'server-only'
import { Pool } from 'pg'
import type { Country, Score, Culture, AdvisorySummary, WarningExcerpt } from './types'
import { advisoryReader } from './advisory-reader'
import { operationalHealth } from './operational-health'

const state = globalThis as typeof globalThis & { safetripReaderPool?: Pool }
const SCORE_PROJECTION = `SELECT iso3,safe_trip_score,bert_score,clustering_score,
    (to_jsonb(s)->>'official_us_level')::integer AS official_us_level,
    (to_jsonb(s)->>'official_us_component')::real AS official_us_component,
    (to_jsonb(s)->>'clustering_component')::real AS clustering_component,
    to_jsonb(s)->>'scoring_version' AS scoring_version FROM public.scores s WHERE iso3=$1`

export async function getPublishedScore(iso3: string) {
    // Uses the already configured restricted reader alongside legacy Supabase.
    const {rows}=await advisoryReader().query<Score>(SCORE_PROJECTION,[iso3])
    return rows[0] ?? null
}

export async function getScoringStatus() {
    const db=process.env.SAFETRIP_ADVISORY_DATABASE_URL ? advisoryReader() : reader()
    const {rows}=await db.query(`SELECT
        (SELECT count(*)=6 FROM pg_attribute WHERE attrelid='public.scores'::regclass
            AND NOT attisdropped AND attname IN ('official_us_level','official_us_component',
                'clustering_component','scoring_version','score_run_id','score_published_at')) AS schema_ready,
        count(*) FILTER(WHERE to_jsonb(s)->>'scoring_version'='us-official-cluster-v1')::integer AS published_rows
        FROM public.scores s`)
    return {supported_formula:'us-official-cluster-v1',regional_policy:'exclude',...rows[0]}
}

export async function getOperationalHealth() {
    const db = process.env.SAFETRIP_ADVISORY_DATABASE_URL ? advisoryReader() : reader()
    const [publication, sources] = await Promise.all([
        db.query(`SELECT
            (SELECT count(*)=6 FROM pg_attribute WHERE attrelid='public.scores'::regclass
                AND NOT attisdropped AND attname IN ('official_us_level','official_us_component',
                    'clustering_component','scoring_version','score_run_id','score_published_at')) AS schema_ready,
            (SELECT count(*)::integer FROM public.countries) AS catalogue_rows,
            count(*) FILTER(WHERE to_jsonb(s)->>'scoring_version'='us-official-cluster-v1'
                AND to_jsonb(s)->>'score_run_id' IS NOT NULL
                AND to_jsonb(s)->>'score_published_at' IS NOT NULL)::integer AS published_rows,
            min((to_jsonb(s)->>'score_published_at')::timestamptz)
                FILTER(WHERE to_jsonb(s)->>'scoring_version'='us-official-cluster-v1') AS oldest_published_at
            FROM public.scores s`),
        db.query(`SELECT source,count(DISTINCT document_id)::integer AS documents,
            min(fetched_at) AS oldest_fetched_at FROM public.advisory_summaries GROUP BY source`),
    ])
    // Source dates measure retrieval, not the age of the government document.
    return operationalHealth(publication.rows[0], sources.rows)
}

export async function getOfficialRefreshStatus() {
    const health = await getOperationalHealth()
    const stamps = Object.values(health.sources).map(source => source.oldest_fetched_at)
    return { published_at: stamps.every(Boolean) ? stamps.sort()[0] : null,
        source_kind: 'us_uk_official', overdue: !Object.values(health.sources).every(source => source.fresh),
        refresh_threshold_hours: health.refresh_threshold_hours,
        score_published_at: health.publication.oldest_published_at, score_overdue: !health.publication.fresh }
}

export async function getCountryAdvisories(iso3: string) {
    const db = process.env.SAFETRIP_ADVISORY_DATABASE_URL ? advisoryReader() : reader()
    const country = await db.query<Pick<Country, 'iso3' | 'name'>>(
        'SELECT iso3, name FROM public.countries WHERE iso3 = $1', [iso3])
    if (!country.rows[0]) return null
    const result = await db.query<AdvisorySummary>(`SELECT iso3, document_id, version_id,
        source, source_url, source_public_updated_at, source_updated_at, source_reviewed_at,
        fetched_at, us_level, uk_alert_status, coverage_scope, region_label
        FROM public.advisory_summaries WHERE iso3 = $1
        ORDER BY source, document_id, coverage_scope, region_label`, [iso3])
    let excerpts: WarningExcerpt[] | null = []
    const regional = result.rows.filter(row => row.source === 'uk_fcdo' && row.uk_alert_status?.some(flag => flag.endsWith('_parts')))
    if (regional.length) {
        try {
            excerpts = (await db.query<WarningExcerpt>(`SELECT version_id, extractor_version,
                section_slug, paragraph_index, warning_heading, heading, body
                FROM public.advisory_warning_excerpts WHERE iso3=$1 AND version_id=ANY($2::uuid[])
                ORDER BY version_id, section_slug, paragraph_index`, [iso3, regional.map(row => row.version_id)])).rows
        } catch {
            // Keep the existing official cards available during staged rollout
            // or a failure of the optional excerpt projection. Never log SQL.
            console.error('Official warning excerpts are temporarily unavailable')
            excerpts = null
        }
    }
    return { country: country.rows[0], sources: {
        us_state: sourceSummary('us_state'), uk_fcdo: sourceSummary('uk_fcdo'),
    } }

    function sourceSummary(source: AdvisorySummary['source']) {
        const documents = result.rows.filter(row => row.source === source).map(row => ({...row,
            warning_excerpts: row.source === 'uk_fcdo' ? excerpts?.filter(e => e.version_id === row.version_id) ?? null : [],
        }))
        // Absence here says nothing about safety, withdrawal, or unresolved mappings.
        return { status: documents.length ? 'available' : 'not_available', documents }
    }
}

export async function getRefreshStatus() {
    const { rows } = await reader().query(`SELECT published_at, source_kind,
        published_at < now() - interval '48 hours' AS overdue
        FROM public.refresh_status WHERE singleton`)
    return rows[0] ?? null
}

function reader() {
    if (!state.safetripReaderPool) {
        const connectionString = process.env.SAFETRIP_DATABASE_URL
        if (!connectionString) throw new Error('Missing reader database URL.')
        const url = new URL(connectionString)
        if (!['postgres:', 'postgresql:'].includes(url.protocol) || url.username !== 'safetrip_reader') {
            throw new Error('A PostgreSQL reader account is required.')
        }
        state.safetripReaderPool = new Pool({
            connectionString,
            max: 2,
            connectionTimeoutMillis: 5000,
            idleTimeoutMillis: 10000,
            statement_timeout: 10000,
            allowExitOnIdle: true,
        })
        state.safetripReaderPool.on('error', () => console.error('Idle database connection failed'))
    }
    return state.safetripReaderPool
}

export async function listCountryScores(query?: string) {
    // Parameters keep user input out of SQL syntax. Escape LIKE wildcards so
    // search means a literal substring rather than a user-supplied SQL pattern.
    const pattern = query?.replace(/[\\%_]/g, '\\$&')
    const result = await reader().query<Country & { safe_trip_score: number | null }>(
        `SELECT c.iso3, c.iso2, c.name, c.continent, c.flag_url, s.safe_trip_score
         FROM public.countries c LEFT JOIN public.scores s ON s.iso3 = c.iso3
         ${query === undefined ? '' : 'WHERE c.name ILIKE $1'}
         ORDER BY c.name, c.iso3 ${query === undefined ? '' : 'LIMIT 10'}`,
        query === undefined ? [] : [`%${pattern}%`],
    )
    return result.rows
}

export async function getCountryDetails(iso3: string) {
    const db = reader()
    const { rows } = await db.query<Country>(
        'SELECT iso3, iso2, name, continent, flag_url FROM public.countries WHERE iso3 = $1', [iso3],
    )
    const country = rows[0]
    if (!country) return null
    const [scores, cultures] = await Promise.all([
        db.query<Score>(SCORE_PROJECTION, [iso3]),
        db.query<Culture>(`SELECT iso3, overview, currency, language, cities, cultural_safety_notes,
            donts, dos, etiquette, food, greeting, religion FROM public.culture WHERE iso3 = $1`, [iso3]),
    ])
    return { country, score: scores.rows[0] ?? null, culture: cultures.rows[0] ?? null }
}

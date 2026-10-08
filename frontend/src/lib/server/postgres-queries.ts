import 'server-only'
import { Pool } from 'pg'
import type { Country, Score, Culture } from './types'

const state = globalThis as typeof globalThis & { safetripReaderPool?: Pool }

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
        db.query<Score>('SELECT iso3, safe_trip_score, bert_score, clustering_score FROM public.scores WHERE iso3 = $1', [iso3]),
        db.query<Culture>(`SELECT iso3, overview, currency, language, cities, cultural_safety_notes,
            donts, dos, etiquette, food, greeting, religion FROM public.culture WHERE iso3 = $1`, [iso3]),
    ])
    return { country, score: scores.rows[0] ?? null, culture: cultures.rows[0] ?? null }
}

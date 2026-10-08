import 'server-only'
import { createClient } from '@supabase/supabase-js'

import type { Country, Score, Culture } from './types'

// Public read role only. Privileged writer credentials never enter this module.
function reader() {
    return createClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        { auth: { persistSession: false, autoRefreshToken: false } }
    )
}

function requireSuccess(error: { code?: string } | null) {
    if (error) {
        console.error('Database read failed', { code: error.code })
        throw new Error('Travel data is temporarily unavailable.')
    }
}

export async function listCountryScores(query?: string) {
    const db = reader()
    let request = db.from('countries').select('iso3, iso2, name, continent, flag_url')
    if (query !== undefined) request = request.ilike('name', `%${query}%`).limit(10)
    const { data: countries, error } = await request.returns<Country[]>()
    requireSuccess(error)
    if (!countries?.length) return []
    const { data: scores, error: scoresError } = await db.from('scores')
        .select('iso3, safe_trip_score, bert_score, clustering_score')
        .in('iso3', countries.map(country => country.iso3)).returns<Score[]>()
    requireSuccess(scoresError)
    const byCountry = new Map(scores?.map(score => [score.iso3, score]))
    return countries.map(country => ({ ...country, safe_trip_score: byCountry.get(country.iso3)?.safe_trip_score ?? null }))
}

export async function getCountryDetails(iso3: string) {
    const db = reader()
    const { data: country, error } = await db.from('countries')
        .select('iso3, iso2, name, continent, flag_url').eq('iso3', iso3).returns<Country[]>().maybeSingle()
    requireSuccess(error)
    if (!country) return null
    const [{ data: score, error: scoreError }, { data: culture, error: cultureError }] = await Promise.all([
        db.from('scores').select('iso3, safe_trip_score, bert_score, clustering_score').eq('iso3', iso3).returns<Score[]>().maybeSingle(),
        db.from('culture').select('iso3, overview, currency, language, cities, cultural_safety_notes, donts, dos, etiquette, food, greeting, religion').eq('iso3', iso3).returns<Culture[]>().maybeSingle(),
    ])
    requireSuccess(scoreError)
    requireSuccess(cultureError)
    return { country, score, culture }
}

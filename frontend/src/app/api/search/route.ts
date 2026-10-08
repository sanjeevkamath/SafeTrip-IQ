import { supabase } from '@/lib/supabaseClient'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url)
    const query = searchParams.get('query')

    if (!query || query.length < 2) {
        return NextResponse.json([])
    }

    try {
        // Perform a search on countries and join with scores
        // Note: This assumes a foreign key relationship exists between countries and scores.
        // If not, we might need to adjust this query.
        // 1. Fetch countries matching the query
        console.log(`Searching for query: "${query}"`);
        const { data: countries, error: countriesError } = await supabase
            .from('countries')
            .select('iso3, name, continent, flag_url')
            .ilike('name', `%${query}%`)
            .limit(10)

        console.log('Countries found:', countries?.length, countries);
        if (countriesError) {
            console.error('Supabase error (countries):', countriesError)
            return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
        }

        if (!countries || countries.length === 0) {
            console.log('No countries found. This might be a Row Level Security (RLS) issue.')
            return NextResponse.json([])
        }

        // 2. Fetch scores for the found countries
        const iso3s = countries.map((c) => c.iso3)
        const { data: scores, error: scoresError } = await supabase
            .from('scores')
            .select('iso3, safe_trip_score')
            .in('iso3', iso3s)

        if (scoresError) {
            console.error('Supabase error (scores):', scoresError)
            // We can still return countries even if scores fail, or error out. 
            // Let's return countries with null scores to be safe.
        }

        // 3. Merge the data manually
        const results = countries.map((country) => {
            const scoreRecord = scores?.find((s) => s.iso3 === country.iso3)
            return {
                iso3: country.iso3,
                name: country.name,
                continent: country.continent,
                flag_url: country.flag_url,
                safe_trip_score: scoreRecord ? scoreRecord.safe_trip_score : null
            }
        })

        return NextResponse.json(results)
    } catch (err) {
        console.error('Unexpected error:', err)
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
    }
}

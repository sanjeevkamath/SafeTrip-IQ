import { supabase } from '@/lib/supabaseClient'
import { NextResponse } from 'next/server'

export async function GET() {
    try {
        // Fetch all countries
        const { data: countries, error: countriesError } = await supabase
            .from('countries')
            .select('iso3, name, flag_url')

        if (countriesError) {
            console.error('Supabase error (countries):', countriesError)
            return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
        }

        if (!countries || countries.length === 0) {
            return NextResponse.json([])
        }

        // Fetch all scores
        const { data: scores, error: scoresError } = await supabase
            .from('scores')
            .select('iso3, safe_trip_score')

        if (scoresError) {
            console.error('Supabase error (scores):', scoresError)
        }

        // Merge data
        const results = countries.map((country) => {
            const scoreRecord = scores?.find((s) => s.iso3 === country.iso3)
            return {
                iso3: country.iso3,
                name: country.name,
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

import { getCountryAdvisories } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
    const iso3 = new URL(request.url).searchParams.get('iso3')?.trim().toUpperCase()
    if (!iso3 || !/^[A-Z]{3}$/.test(iso3)) {
        return NextResponse.json({ error: 'Provide a three-letter country code.' }, { status: 400 })
    }
    try {
        const data = await getCountryAdvisories(iso3)
        if (!data) return NextResponse.json({ error: 'Country not found.' }, { status: 404 })
        return NextResponse.json(data, { headers: { 'Cache-Control': 'no-store' } })
    } catch {
        return NextResponse.json({ error: 'Advisory data is temporarily unavailable.' }, { status: 503 })
    }
}

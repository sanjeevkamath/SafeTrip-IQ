import { listCountryScores } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
    const query = new URL(request.url).searchParams.get('query')?.trim()
    if (!query || query.length < 2) return NextResponse.json([])
    try {
        return NextResponse.json(await listCountryScores(query))
    } catch {
        return NextResponse.json({ error: 'Travel data is temporarily unavailable.' }, { status: 503 })
    }
}

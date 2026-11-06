import { listCountryScores } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

// Infrastructure readiness is separate from the age of official data.
export async function GET() {
    try {
        await listCountryScores('CANADA')
        return NextResponse.json({ status: 'ok' }, { headers: { 'Cache-Control': 'no-store' } })
    } catch {
        return NextResponse.json({ status: 'unavailable' }, {
            status: 503, headers: { 'Cache-Control': 'no-store' },
        })
    }
}

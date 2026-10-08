import { listCountryScores } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
    try {
        await listCountryScores('CANADA')
        return NextResponse.json({ status: 'ok' })
    } catch {
        return NextResponse.json({ status: 'unavailable' }, { status: 503 })
    }
}

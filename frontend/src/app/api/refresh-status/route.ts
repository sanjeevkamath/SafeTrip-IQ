import { getRefreshStatus } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
    try {
        return NextResponse.json(await getRefreshStatus(), { headers: { 'Cache-Control': 'no-store' } })
    } catch {
        return NextResponse.json({ error: 'Refresh status unavailable.' }, { status: 503 })
    }
}

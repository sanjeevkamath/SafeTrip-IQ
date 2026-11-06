import { getOperationalHealth } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
    try {
        const health = await getOperationalHealth()
        return NextResponse.json(health, {
            status: health.healthy ? 200 : 503, headers: { 'Cache-Control': 'no-store' },
        })
    } catch {
        return NextResponse.json({ healthy: false, error: 'Data health is temporarily unavailable.' }, {
            status: 503, headers: { 'Cache-Control': 'no-store' },
        })
    }
}

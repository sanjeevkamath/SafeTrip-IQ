import { getScoringStatus } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export const dynamic='force-dynamic'
export async function GET() {
    try {
        return NextResponse.json(await getScoringStatus(),{headers:{'Cache-Control':'no-store'}})
    } catch {
        return NextResponse.json({error:'Scoring status is temporarily unavailable.'},{status:503})
    }
}

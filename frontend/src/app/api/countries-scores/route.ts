import { listCountryScores } from '@/lib/server/queries'
import { NextResponse } from 'next/server'

export async function GET() {
    try {
        return NextResponse.json(await listCountryScores())
    } catch {
        return NextResponse.json({ error: 'Travel data is temporarily unavailable.' }, { status: 503 })
    }
}

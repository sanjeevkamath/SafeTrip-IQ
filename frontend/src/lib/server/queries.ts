import 'server-only'
import * as postgres from './postgres-queries'
import * as supabase from './supabase-queries'
export type { Country, Score, Culture } from './types'

function adapter() {
    const backend = process.env.SAFETRIP_DB_BACKEND ?? 'supabase'
    if (backend === 'postgres') return postgres
    if (backend === 'supabase') return supabase
    throw new Error('Unsupported database backend.')
}

async function read<T>(operation: () => Promise<T>): Promise<T> {
    try {
        return await operation()
    } catch {
        // Driver errors can contain SQL, connection details, or input data.
        console.error('Database read failed')
        throw new Error('Travel data is temporarily unavailable.')
    }
}

export function listCountryScores(query?: string) {
    return read(() => adapter().listCountryScores(query))
}

export function getCountryDetails(iso3: string) {
    return read(() => adapter().getCountryDetails(iso3))
}

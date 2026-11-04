import 'server-only'
import { Pool } from 'pg'

export function advisoryPoolOptions(connectionString: string, ca?: string) {
    const url = new URL(connectionString)
    if (!['postgres:', 'postgresql:'].includes(url.protocol)) throw new Error('Invalid database protocol.')
    // Explicit TLS options must not be replaced by connection-string SSL options.
    if (url.search || url.hash) throw new Error('Use the separate CA setting; database URL parameters are unsupported.')
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    const pooler = url.hostname.endsWith('.pooler.supabase.com') && url.port === '5432'
    const expected = local ? url.username === 'safetrip_reader'
        : pooler && /^safetrip_reader\.[a-z0-9]+$/.test(url.username)
    if (!expected || (!local && !ca)) throw new Error('A restricted reader and verified CA are required.')
    return {
        connectionString,
        ssl: local ? undefined : { ca, rejectUnauthorized: true },
        max: 2, connectionTimeoutMillis: 5000, idleTimeoutMillis: 10000,
        statement_timeout: 10000, allowExitOnIdle: true,
    }
}

const state = globalThis as typeof globalThis & { safetripAdvisoryPool?: Pool }
export function advisoryReader() {
    if (!state.safetripAdvisoryPool) {
        const url = process.env.SAFETRIP_ADVISORY_DATABASE_URL
        if (!url) throw new Error('Missing advisory reader URL.')
        state.safetripAdvisoryPool = new Pool(advisoryPoolOptions(url, process.env.SAFETRIP_ADVISORY_DATABASE_CA))
        state.safetripAdvisoryPool.on('error', () => console.error('Idle advisory connection failed'))
    }
    return state.safetripAdvisoryPool
}

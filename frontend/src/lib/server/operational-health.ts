// Seven-day refresh interval plus two days of scheduling/recovery slack.
export const FRESHNESS_HOURS = 216

type Source = { source: string; oldest_fetched_at: string | Date | null; documents: number }
type Publication = { schema_ready: boolean; published_rows: number; catalogue_rows: number;
    oldest_published_at: string | Date | null }

export function operationalHealth(publication: Publication, sources: Source[], now = Date.now()) {
    const stamp = (value: string | Date | null) => value ? new Date(value).toISOString() : null
    const recent = (value: string | Date | null) => {
        if (!value) return false
        const age = now - new Date(value).getTime()
        return Number.isFinite(age) && age >= -5 * 60_000 && age <= FRESHNESS_HOURS * 3600_000
    }
    const sourceStatus = Object.fromEntries(['us_state', 'uk_fcdo'].map(source => {
        const row = sources.find(s => s.source === source)
        return [source, { documents: row?.documents ?? 0, oldest_fetched_at: stamp(row?.oldest_fetched_at ?? null),
            fresh: Boolean(row && row.documents > 0 && recent(row.oldest_fetched_at)) }]
    }))
    const adviceFresh = Object.values(sourceStatus).every(source => source.fresh)
    const scoresFresh = publication.schema_ready && publication.catalogue_rows > 0
        && publication.published_rows === publication.catalogue_rows && recent(publication.oldest_published_at)
    return { healthy: adviceFresh && scoresFresh, checked_at: new Date(now).toISOString(),
        refresh_threshold_hours: FRESHNESS_HOURS, sources: sourceStatus,
        publication: { ...publication, oldest_published_at: stamp(publication.oldest_published_at), fresh: scoresFresh } }
}

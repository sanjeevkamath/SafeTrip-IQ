export type Country = {
    iso3: string
    iso2: string | null
    name: string
    continent: string | null
    flag_url: string | null
}
export type AdvisorySummary = {
    iso3: string
    document_id: string
    version_id: string
    source: 'us_state' | 'uk_fcdo'
    source_url: string
    source_public_updated_at: string | null
    source_updated_at: string | null
    source_reviewed_at: string | null
    fetched_at: string
    us_level: number | null
    uk_alert_status: string[] | null
    coverage_scope: 'whole_country' | 'parts'
    region_label: string | null
    warning_excerpts?: WarningExcerpt[] | null
}
export type WarningExcerpt = {
    version_id: string
    extractor_version: string
    section_slug: string
    paragraph_index: number
    warning_heading: string
    heading: string | null
    body: string
}
export type Score = {
    iso3: string
    safe_trip_score: number | null
    bert_score: number | null
    clustering_score: number | null
}
export type Culture = {
    iso3: string
    overview: string | null
    currency: string | null
    language: string | null
    cities: string | null
    cultural_safety_notes: string | null
    donts: string | null
    dos: string | null
    etiquette: string | null
    food: string | null
    greeting: string | null
    religion: string | null
}


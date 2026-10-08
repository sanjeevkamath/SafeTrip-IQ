export type Country = {
    iso3: string
    iso2: string | null
    name: string
    continent: string | null
    flag_url: string | null
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


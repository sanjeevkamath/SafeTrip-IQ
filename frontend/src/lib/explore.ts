import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'

export type Destination = {
    iso3: string
    iso2: string | null
    name: string
    continent: string | null
    flag_url: string | null
    safe_trip_score: number | null
}

export type MapCountry = {
    iso3: string
    name: string
    continent: string
    center: [number, number]
    rank: number
}

export type WorldGeometry = FeatureCollection<Polygon | MultiPolygon, MapCountry>

export type GlobeCamera = { longitude: number; latitude: number; zoom: number }

export const initialCamera: GlobeCamera = { longitude: -15, latitude: 20, zoom: 1 }

export const featuredDestinations = [
    { iso3: 'PRT', name: 'Portugal', detail: 'Atlantic coast & local traditions' },
    { iso3: 'MAR', name: 'Morocco', detail: 'Markets, mountains & medinas' },
    { iso3: 'ISL', name: 'Iceland', detail: 'Wild landscapes & open roads' },
] as const

'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
    ComposableMap,
    Geographies,
    Geography,
    ZoomableGroup
} from 'react-simple-maps'
import { scaleLinear } from 'd3-scale'

const geoUrl = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson'

interface CountryScore {
    iso3: string
    name: string
    safe_trip_score: number | null
}

export default function WorldMap() {
    const [countryData, setCountryData] = useState<Record<string, { score: number | null, flag_url: string | null, name: string }>>({})
    const [hoveredCountry, setHoveredCountry] = useState<{ name: string, score: number | null, flag_url: string | null } | null>(null)
    const [loading, setLoading] = useState(true)
    const router = useRouter()

    useEffect(() => {
        fetch('/api/countries-scores')
            .then(res => res.json())
            .then((data: any[]) => {
                const dataMap: Record<string, { score: number | null, flag_url: string | null, name: string }> = {}
                data.forEach(country => {
                    dataMap[country.iso3] = {
                        score: country.safe_trip_score,
                        flag_url: country.flag_url,
                        name: country.name
                    }
                })
                setCountryData(dataMap)
                setLoading(false)
            })
            .catch(err => {
                console.error('Failed to load country scores:', err)
                setLoading(false)
            })
    }, [])

    // Color scale: red (0) -> yellow (5) -> green (10)
    const colorScale = scaleLinear<string>()
        .domain([0, 4, 7, 10])
        .range(['#8B0000', '#CC3300', '#CCCC00', '#008000'])
        .clamp(true)

    const getCountryColor = (geo: any): string => {
        let iso3 = geo.properties.ISO_A3
        if (!iso3 || iso3 === '-99' || iso3.startsWith('-')) {
            iso3 = geo.properties.ADM0_A3 || geo.properties.ISO_A3_EH
        }
        iso3 = iso3?.toUpperCase()
        if (!iso3) return '#d4d4d8' // gray for unknown

        const data = countryData[iso3]
        if (!data || data.score === null) return '#d4d4d8' // gray for no data

        return colorScale(data.score)
    }

    const [position, setPosition] = useState({ coordinates: [0, 0], zoom: 1 })

    const handleZoomIn = () => {
        if (position.zoom >= 4) return
        setPosition(pos => ({ ...pos, zoom: pos.zoom * 1.5 }))
    }

    const handleZoomOut = () => {
        if (position.zoom <= 1) return
        setPosition(pos => ({ ...pos, zoom: pos.zoom / 1.5 }))
    }

    const handleMoveEnd = (position: { coordinates: [number, number], zoom: number }) => {
        setPosition(position)
    }

    if (loading) {
        return (
            <div className="w-full h-[500px] flex items-center justify-center bg-gray-50 rounded-xl">
                <p className="text-gray-500">Loading map data...</p>
            </div>
        )
    }

    return (
        <div className="w-full relative">
            <div className="absolute right-4 top-4 flex flex-col gap-2 z-10">
                <button
                    onClick={handleZoomIn}
                    className="w-8 h-8 flex items-center justify-center bg-white rounded-md shadow-md hover:bg-gray-50 text-gray-700 font-bold border border-gray-200"
                    aria-label="Zoom in"
                >
                    +
                </button>
                <button
                    onClick={handleZoomOut}
                    className="w-8 h-8 flex items-center justify-center bg-white rounded-md shadow-md hover:bg-gray-50 text-gray-700 font-bold border border-gray-200"
                    aria-label="Zoom out"
                >
                    −
                </button>
            </div>

            <ComposableMap
                projectionConfig={{
                    scale: 147
                }}
                style={{
                    width: '100%',
                    height: 'auto'
                }}
            >
                <ZoomableGroup
                    zoom={position.zoom}
                    center={position.coordinates as [number, number]}
                    onMoveEnd={handleMoveEnd}
                    minZoom={1}
                    maxZoom={4}
                >
                    <Geographies geography={geoUrl}>
                        {({ geographies }: { geographies: any[] }) =>
                            geographies.map((geo: any) => {
                                let iso3 = geo.properties.ISO_A3
                                if (!iso3 || iso3 === '-99' || iso3.startsWith('-')) {
                                    iso3 = geo.properties.ADM0_A3 || geo.properties.ISO_A3_EH
                                }
                                iso3 = iso3?.toUpperCase()
                                const data = countryData[iso3]

                                return (
                                    <Geography
                                        key={geo.rsmKey}
                                        geography={geo}
                                        fill={getCountryColor(geo)}
                                        stroke="#fff"
                                        strokeWidth={0.5}
                                        style={{
                                            default: { outline: 'none' },
                                            hover: {
                                                fill: '#3b82f6',
                                                outline: 'none',
                                                cursor: 'pointer'
                                            },
                                            pressed: { outline: 'none' }
                                        }}
                                        onMouseEnter={() => {
                                            const name = geo.properties.NAME || geo.properties.name || 'Unknown'
                                            setHoveredCountry({
                                                name,
                                                score: data?.score ?? null,
                                                flag_url: data?.flag_url ?? null
                                            })
                                        }}
                                        onMouseLeave={() => {
                                            setHoveredCountry(null)
                                        }}
                                        onClick={() => {
                                            if (iso3 && data) {
                                                router.push(`/country/${iso3}`)
                                            }
                                        }}
                                    />
                                )
                            })
                        }
                    </Geographies>
                </ZoomableGroup>
            </ComposableMap>

            {/* Tooltip */}
            {hoveredCountry && (
                <div className="absolute top-4 left-4 bg-black/90 text-white px-4 py-3 rounded-lg text-sm pointer-events-none shadow-xl border border-gray-700 flex items-center gap-3 z-50">
                    {hoveredCountry.flag_url && (
                        <img
                            src={hoveredCountry.flag_url}
                            alt={`${hoveredCountry.name} flag`}
                            className="w-8 h-6 object-cover rounded shadow-sm border border-gray-600"
                        />
                    )}
                    <div>
                        <div className="font-bold text-base">{hoveredCountry.name}</div>
                        <div className={hoveredCountry.score !== null ?
                            (hoveredCountry.score >= 7 ? "text-green-400" :
                                hoveredCountry.score >= 4 ? "text-yellow-400" : "text-red-400")
                            : "text-gray-400"}>
                            {hoveredCountry.score !== null
                                ? `Safety Score: ${hoveredCountry.score.toFixed(1)}/10`
                                : 'No safety data available'}
                        </div>
                    </div>
                </div>
            )}

            {/* Legend */}
            {/*         .range(['#8B0000', '#CC3300', '#CCCC00', '#008000']) */}
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 mt-4 text-sm px-4">
                <span className="text-gray-600 font-medium">Safety Score:</span>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#8B0000' }}></div>
                    <span className="text-gray-600">Low (0-4)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#CC3300' }}></div>
                    <span className="text-gray-600">Medium (4-7)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#CCCC00' }}></div>
                    <span className="text-gray-600">High (8-9.9)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#008000' }}></div>
                    <span className="text-gray-600">Extremely High (10)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gray-300"></div>
                    <span className="text-gray-600">No Data</span>
                </div>
            </div>        </div>
    )
}

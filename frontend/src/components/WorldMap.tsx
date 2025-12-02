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
    const [scores, setScores] = useState<Record<string, number>>({})
    const [tooltipContent, setTooltipContent] = useState('')
    const [loading, setLoading] = useState(true)
    const router = useRouter()

    useEffect(() => {
        fetch('/api/countries-scores')
            .then(res => res.json())
            .then((data: CountryScore[]) => {
                console.log('Loaded country scores:', data.length, 'countries')
                console.log('Sample scores:', data.slice(0, 5))
                const scoresMap: Record<string, number> = {}
                data.forEach(country => {
                    if (country.safe_trip_score !== null) {
                        scoresMap[country.iso3] = country.safe_trip_score
                    }
                })
                console.log('Scores map keys (first 10):', Object.keys(scoresMap).slice(0, 10))
                setScores(scoresMap)
                setLoading(false)
            })
            .catch(err => {
                console.error('Failed to load country scores:', err)
                setLoading(false)
            })
    }, [])

    // Color scale: red (0) -> yellow (5) -> green (10)
    const colorScale = scaleLinear<string>()
        .domain([0, 5, 10])
        .range(['#ef4444', '#f59e0b', '#22c55e'])
        .clamp(true)

    const getCountryColor = (geo: any): string => {
        let iso3 = geo.properties.ISO_A3
        if (!iso3 || iso3 === '-99' || iso3.startsWith('-')) {
            iso3 = geo.properties.ADM0_A3 || geo.properties.ISO_A3_EH
        }
        iso3 = iso3?.toUpperCase()
        if (!iso3) return '#d4d4d8' // gray for unknown

        const score = scores[iso3]
        if (score === undefined) return '#d4d4d8' // gray for no data

        return colorScale(score)
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
            <ComposableMap
                projectionConfig={{
                    scale: 147
                }}
                style={{
                    width: '100%',
                    height: 'auto'
                }}
            >
                <ZoomableGroup>
                    <Geographies geography={geoUrl}>
                        {({ geographies }: { geographies: any[] }) =>
                            geographies.map((geo: any) => {
                                // Natural Earth uses ISO_A3, but it can be "-99" for disputed territories
                                // Use ADM0_A3 or ISO_A3_EH as fallback which are more reliable
                                let iso3 = geo.properties.ISO_A3
                                if (!iso3 || iso3 === '-99' || iso3.startsWith('-')) {
                                    iso3 = geo.properties.ADM0_A3 || geo.properties.ISO_A3_EH
                                }
                                iso3 = iso3?.toUpperCase()
                                const score = scores[iso3]

                                // Debug log for countries without scores
                                const countryName = geo.properties.NAME || geo.properties.name
                                if (iso3 && score === undefined && ['FRANCE', 'NORWAY', 'SOMALIA'].includes(countryName?.toUpperCase())) {
                                    console.log(`Missing score for ${countryName}:`, {
                                        ISO_A3: geo.properties.ISO_A3,
                                        ADM0_A3: geo.properties.ADM0_A3,
                                        ISO_A3_EH: geo.properties.ISO_A3_EH,
                                        computed_iso3: iso3,
                                        all_properties: geo.properties
                                    })
                                }

                                // Debug log for first few countries
                                if (Object.keys(scores).length > 0 && Math.random() < 0.05) {
                                    console.log('Map geo debug:', {
                                        name: geo.properties.NAME || geo.properties.name,
                                        ISO_A3: geo.properties.ISO_A3,
                                        ADM0_A3: geo.properties.ADM0_A3,
                                        computed_iso3: iso3,
                                        has_score: score !== undefined,
                                        score: score
                                    })
                                }

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
                                            const scoreText = score !== undefined
                                                ? `Score: ${score.toFixed(1)}/10`
                                                : 'No data'
                                            setTooltipContent(`${name} - ${scoreText}`)
                                        }}
                                        onMouseLeave={() => {
                                            setTooltipContent('')
                                        }}
                                        onClick={() => {
                                            if (iso3 && scores[iso3] !== undefined) {
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
            {tooltipContent && (
                <div className="absolute top-4 left-4 bg-black/80 text-white px-3 py-2 rounded-lg text-sm pointer-events-none">
                    {tooltipContent}
                </div>
            )}

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 mt-4 text-sm">
                <span className="text-gray-600">Safety Score:</span>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#ef4444' }}></div>
                    <span className="text-gray-600">Low (0-3)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#f59e0b' }}></div>
                    <span className="text-gray-600">Medium (4-7)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: '#22c55e' }}></div>
                    <span className="text-gray-600">High (8-10)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gray-300"></div>
                    <span className="text-gray-600">No Data</span>
                </div>
            </div>
        </div>
    )
}

'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'
import { featuredDestinations, initialCamera, type Destination, type GlobeCamera, type WorldGeometry } from '@/lib/explore'
import RefreshStatus from './RefreshStatus'
import CountryFlag from './CountryFlag'
import SearchBar from './SearchBar'
import WorldMap from './WorldMap'
import styles from './ExploreHome.module.css'
import palette from './AtlanticSand.module.css'

export default function ExploreHome() {
    const router = useRouter()
    const [geometry, setGeometry] = useState<WorldGeometry>()
    const [geometryFailed, setGeometryFailed] = useState(false)
    const [catalogue, setCatalogue] = useState<Destination[]>()
    const [catalogueFailed, setCatalogueFailed] = useState(false)
    const [camera, setCamera] = useState<GlobeCamera>(initialCamera)
    const [hovered, setHovered] = useState<string | null>(null)
    const [selected, setSelected] = useState<string | null>(null)
    const [searchDestination, setSearchDestination] = useState<Destination>()
    const [searchOpen, setSearchOpen] = useState(false)
    const [searchVersion, setSearchVersion] = useState(0)

    useEffect(() => {
        const controller = new AbortController()
        async function load<T>(url: string, receive: (data: T) => void, fail: () => void) {
            try {
                const response = await fetch(url, { signal: controller.signal })
                if (!response.ok) throw new Error('Destination data unavailable')
                const data: T = await response.json()
                if (!controller.signal.aborted) receive(data)
            } catch {
                if (!controller.signal.aborted) fail()
            }
        }
        void load<WorldGeometry>('/globe/countries.geojson', setGeometry, () => setGeometryFailed(true))
        void load<Destination[]>('/api/countries-scores', setCatalogue, () => setCatalogueFailed(true))
        return () => controller.abort()
    }, [])

    const locations = useMemo(() => new Map(geometry?.features.map(feature => [feature.properties.iso3, feature.properties])), [geometry])
    const countries = useMemo(() => new Map(catalogue?.map(country => [country.iso3, country])), [catalogue])
    const active = hovered ?? selected
    const isActiveSelected = active !== null && active === selected
    const location = active ? locations.get(active) : undefined
    const data = active ? countries.get(active) ?? (searchDestination?.iso3 === active ? searchDestination : undefined) : undefined
    const featured = featuredDestinations.find(country => country.iso3 === active)
    const countryName = data?.name ?? location?.name ?? featured?.name
    const continent = data?.continent ?? location?.continent

    function selectCountry(iso3: string, center = false) {
        setHovered(null)
        setSelected(iso3)
        const location = locations.get(iso3)
        if (center && location) {
            const [longitude, latitude] = location.center
            setCamera({ longitude, latitude, zoom: 1 })
        }
    }

    function clearSelection() {
        setSelected(null)
        setHovered(null)
    }

    function resetView() {
        clearSelection()
        setCamera(initialCamera)
        setSearchDestination(undefined)
        setSearchOpen(false)
        setSearchVersion(version => version + 1)
    }

    return (
        <main className={`${palette.theme} ${styles.home}`}>
            <header className={styles.brand}>
                <button type="button" aria-label="SafeTrip IQ, reset view" onClick={resetView}>
                    SafeTrip <span>IQ</span>
                </button>
            </header>
            <div className={styles.rail}>
                <SearchBar key={searchVersion} onOpenChange={setSearchOpen} onSelect={destination => {
                    setSearchDestination(destination)
                    selectCountry(destination.iso3, true)
                }} />
                <div className={styles.sidebar}>
                    {!searchOpen && (countryName ? (
                        <section className={styles.preview} aria-label="Country preview">
                            <div>
                                {continent && <p className={styles.region}>{continent}</p>}
                                <div className={styles.countryHeading}>
                                    {data && <CountryFlag flagUrl={data.flag_url} iso2={data.iso2}
                                        className={styles.flag} fallbackClassName={styles.flagEmoji} />}
                                    <h2>{countryName}</h2>
                                </div>
                                {featured && <p>{featured.detail}</p>}
                            </div>
                            <div>
                                <h3>SafeTrip score</h3>
                                {data?.safe_trip_score != null ? <>
                                    <p className={styles.score}><strong>{data.safe_trip_score.toFixed(1)}</strong> / 10</p>
                                    <p className={styles.explanation}>Custom travel safety index.</p>
                                </> : <p>{catalogue || catalogueFailed ? 'Score unavailable' : 'Checking score…'}</p>}
                            </div>
                            {data && <div>
                                <h3>Official travel advice</h3>
                                <p className={styles.explanation}>See the country guide for available US and UK guidance.</p>
                            </div>}
                            {isActiveSelected ? <>
                                {data && <Link href={`/country/${data.iso3}`} className={styles.guideLink}>
                                    View country guide <ArrowRight size={15} aria-hidden="true" />
                                </Link>}
                                <button type="button" className={styles.textAction} onClick={clearSelection}>Clear selection</button>
                            </> : !selected && active && <button type="button" className={styles.textAction} onClick={() => selectCountry(active)}>
                                Keep this preview open <ArrowRight size={15} aria-hidden="true" />
                            </button>}
                        </section>
                    ) : (
                        <section className={styles.discovery}>
                            <h1>Where to<br /> next?</h1>
                            <p>Explore destinations and check travel advice before you go.</p>
                            <div className={styles.featured}>
                                <h2>Places to explore</h2>
                                {featuredDestinations.map(country =>
                                    <button key={country.iso3} type="button" onClick={() => selectCountry(country.iso3, true)}>
                                        <span>{country.name}<small>{country.detail}</small></span>
                                        <ArrowRight size={16} aria-hidden="true" />
                                    </button>
                                )}
                            </div>
                        </section>
                    ))}
                </div>
                <div className={styles.railFooter}>
                    {!searchOpen && <p className={styles.hoverHelp}>Hover to preview. Click to pin. Double-click for the guide.</p>}
                    {catalogueFailed && <p className={styles.overdue} role="alert">Country scores are temporarily unavailable.</p>}
                    <RefreshStatus />
                </div>
            </div>
            <WorldMap geometry={geometry} failed={geometryFailed} camera={camera} onCameraChange={setCamera}
                active={active} onPreview={setHovered} onSelect={selectCountry}
                onLeaveGlobe={() => { if (selected) setHovered(null) }}
                onOpenCountry={iso3 => {
                    if (countries.has(iso3) || searchDestination?.iso3 === iso3) router.push(`/country/${iso3}`)
                }}
                countries={countries} />
        </main>
    )
}

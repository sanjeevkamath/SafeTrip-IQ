'use client'

import { geoDistance, geoOrthographic, geoPath } from 'd3-geo'
import { Minus, Plus, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type Dispatch, type PointerEvent, type SetStateAction } from 'react'
import { initialCamera, type Destination, type GlobeCamera, type WorldGeometry } from '@/lib/explore'
import styles from './ExploreHome.module.css'

const size = 1040
const center = size / 2
const radius = 488
const minZoom = 0.8
const maxZoom = 2.5
const atlanticLabels = new Set(['ISL', 'NOR', 'GBR', 'FRA', 'PRT', 'TUR', 'MAR', 'DZA', 'EGY', 'NGA', 'BRA'])
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

type Drag = { id: number; x: number; y: number; moved: boolean; start: GlobeCamera; degreesPerPixel: number }

function zoomCamera(camera: GlobeCamera, factor: number): GlobeCamera {
    const zoom = clamp(camera.zoom * factor, minZoom, maxZoom)
    return zoom === camera.zoom ? camera : { ...camera, zoom }
}

export default function WorldMap({ geometry, failed, camera, onCameraChange, active, onPreview, onSelect, onReset, onOpenCountry, countries }: {
    geometry?: WorldGeometry
    failed: boolean
    camera: GlobeCamera
    onCameraChange: Dispatch<SetStateAction<GlobeCamera>>
    active: string | null
    onPreview: (iso3: string | null) => void
    onSelect: (iso3: string) => void
    onReset: () => void
    onOpenCountry: (iso3: string) => void
    countries: Map<string, Destination>
}) {
    const surface = useRef<HTMLDivElement>(null)
    const drag = useRef<Drag | null>(null)
    const suppressClick = useRef(false)
    const [surfaceWidth, setSurfaceWidth] = useState(size)
    const { longitude, latitude, zoom } = camera
    const atHome = longitude === initialCamera.longitude && latitude === initialCamera.latitude && zoom === 1
    const labelSize = Math.max(13, 11 * size / surfaceWidth)
    const labelHeight = Math.max(26, labelSize * 1.8)

    useEffect(() => {
        const viewport = surface.current
        if (!viewport) return
        const observer = new ResizeObserver(([entry]) => {
            if (entry.contentRect.width) setSurfaceWidth(entry.contentRect.width)
        })
        observer.observe(viewport)
        const onWheel = (event: WheelEvent) => {
            if (!event.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return
            event.preventDefault()
            const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1
            onCameraChange(previous => zoomCamera(previous, Math.exp(-event.deltaY * unit * 0.0016)))
        }
        viewport.addEventListener('wheel', onWheel, { passive: false })
        return () => {
            observer.disconnect()
            viewport.removeEventListener('wheel', onWheel)
        }
    }, [onCameraChange])

    const projection = useMemo(() => geoOrthographic().translate([center, center]).scale(radius)
        .rotate([-longitude, -latitude]).clipAngle(90).precision(0.35), [longitude, latitude])

    const shapes = useMemo(() => {
        const path = geoPath(projection).digits(1)
        return (geometry?.features ?? []).flatMap(feature => {
            const d = path(feature)
            return d ? [{ country: feature.properties, d }] : []
        })
    }, [geometry, projection])

    const labels = useMemo(() => {
        const origin: [number, number] = [longitude, latitude]
        const candidates = shapes.map(({ country }) => ({ country, distance: geoDistance(origin, country.center) }))
            .filter(({ country, distance }) => distance < 1.4 &&
                (!atHome || country.iso3 === active || atlanticLabels.has(country.iso3)))
            .sort((a, b) => Number(b.country.iso3 === active) - Number(a.country.iso3 === active) ||
                Number(b.country.iso3 === 'PRT' && atHome) - Number(a.country.iso3 === 'PRT' && atHome) ||
                a.country.rank - b.country.rank || a.distance - b.distance)

        const placed: { iso3: string; name: string; x: number; y: number; halfWidth: number }[] = []
        for (const { country } of candidates) {
            const point = projection(country.center)
            if (!point) continue
            const [pointX, y] = point.map(coordinate => center + (coordinate - center) * zoom)
            const x = country.iso3 === 'PRT' && atHome ? pointX - 65 : pointX
            const name = countries.get(country.iso3)?.name ?? country.name
            const halfWidth = Math.max(labelSize * 1.8, name.length * labelSize * 0.3)
            if (x - halfWidth < 0 || x + halfWidth > size || y < labelHeight || y > size - labelHeight) continue
            if (placed.some(other => Math.abs(y - other.y) < labelHeight &&
                Math.abs(x - other.x) < halfWidth + other.halfWidth + 8)) continue
            placed.push({ iso3: country.iso3, name, x, y, halfWidth })
            if (placed.length >= (zoom > 1.5 ? 18 : 12)) break
        }
        return placed
    }, [active, atHome, countries, labelHeight, labelSize, latitude, longitude, projection, shapes, zoom])

    function startDrag(event: PointerEvent<HTMLDivElement>) {
        if (!event.isPrimary || event.button !== 0) return
        const width = event.currentTarget.getBoundingClientRect().width
        if (!width) return
        suppressClick.current = false
        drag.current = {
            id: event.pointerId, x: event.clientX, y: event.clientY, start: camera, moved: false,
            degreesPerPixel: 112 / (width * zoom),
        }
    }

    function moveDrag(event: PointerEvent<HTMLDivElement>) {
        const current = drag.current
        if (!current || event.pointerId !== current.id) return
        const dx = event.clientX - current.x
        const dy = event.clientY - current.y
        if (!current.moved && Math.hypot(dx, dy) < 4) return
        if (!current.moved) {
            current.moved = true
            suppressClick.current = true
            onPreview(null)
            event.currentTarget.setPointerCapture(event.pointerId)
        }
        onCameraChange(previous => ({
            ...previous,
            longitude: current.start.longitude - dx * current.degreesPerPixel,
            latitude: clamp(current.start.latitude + dy * current.degreesPerPixel, -85, 85),
        }))
    }

    function finishDrag(event: PointerEvent<HTMLDivElement>) {
        if (drag.current?.id === event.pointerId) drag.current = null
    }

    function changeZoom(factor: number) {
        onCameraChange(previous => zoomCamera(previous, factor))
    }

    return (
        <section className={styles.map} aria-label="Explore the globe">
            <div ref={surface} className={styles.globeSurface}
                onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={finishDrag} onPointerCancel={finishDrag}
                onLostPointerCapture={finishDrag}
                onDragStart={event => event.preventDefault()}
                onPointerOver={event => {
                    if (event.pointerType !== 'mouse' || drag.current || !(event.target instanceof Element)) return
                    onPreview(event.target.closest('[data-country]')?.getAttribute('data-country') ?? null)
                }}
                onPointerLeave={event => {
                    if (drag.current?.moved) return
                    finishDrag(event)
                    onPreview(null)
                }}
            >
                <svg viewBox={`0 0 ${size} ${size}`} className={styles.globe}
                    role="group" aria-label="World globe. Use arrow keys to rotate." tabIndex={0}
                    onKeyDown={event => {
                        if (event.target !== event.currentTarget) return
                        const horizontal = event.key === 'ArrowLeft' ? -15 : event.key === 'ArrowRight' ? 15 : 0
                        const vertical = event.key === 'ArrowUp' ? 15 : event.key === 'ArrowDown' ? -15 : 0
                        if (!horizontal && !vertical) return
                        event.preventDefault()
                        onPreview(null)
                        onCameraChange(previous => ({
                            ...previous,
                            longitude: previous.longitude + horizontal,
                            latitude: clamp(previous.latitude + vertical, -85, 85),
                        }))
                    }}
                >
                    <g transform={`translate(${center} ${center}) scale(${zoom}) translate(-${center} -${center})`}>
                        <image href="/globe/atmosphere.svg" x={26} y={26} width={988} height={988} />
                        <image href="/globe/ocean.svg" x={32} y={32} width={976} height={976} />
                        {shapes.map(({ country, d }) => <path key={country.iso3} d={d} data-country={country.iso3}
                            className={styles.land} data-active={country.iso3 === active}
                            onClick={() => { if (!suppressClick.current) onSelect(country.iso3) }}
                            onDoubleClick={() => { if (!suppressClick.current) onOpenCountry(country.iso3) }}
                        />)}
                        <g pointerEvents="none">
                            <image href="/globe/shading.svg" x={32} y={32} width={976} height={976} />
                            <image href="/globe/rim.svg" x={32} y={32} width={976} height={976} opacity={0.45} />
                        </g>
                    </g>
                    {atHome && surfaceWidth >= 500 && <text x={242} y={452} className={styles.oceanLabel}>Atlantic Ocean</text>}
                    {labels.map(({ iso3, name, x, y, halfWidth }) =>
                        <g key={iso3} className={styles.countryLabel} role="button" tabIndex={0}
                            aria-label={`Select ${name} on the globe`} data-country={iso3} data-active={iso3 === active}
                            onFocus={event => {
                                if (event.currentTarget.matches(':focus-visible')) onPreview(iso3)
                            }}
                            onBlur={() => onPreview(null)}
                            onClick={() => { if (!suppressClick.current) onSelect(iso3) }}
                            onDoubleClick={() => { if (!suppressClick.current) onOpenCountry(iso3) }}
                            onKeyDown={event => {
                                if (event.key !== 'Enter' && event.key !== ' ') return
                                event.preventDefault()
                                onSelect(iso3)
                            }}>
                            <rect x={x - halfWidth} y={y - labelHeight / 2} width={halfWidth * 2} height={labelHeight} fill="transparent" />
                            <text x={x} y={y} fontSize={labelSize} dominantBaseline="central" textAnchor="middle">{name}</text>
                        </g>
                    )}
                    <circle className={styles.globeFocus} cx={center} cy={center} r={radius}
                        vectorEffect="non-scaling-stroke" aria-hidden="true" />
                </svg>
            </div>
            {failed && <p className={styles.mapMessage} role="alert">Map data is temporarily unavailable. You can still search for a country.</p>}
            {!failed && !geometry && <p className={styles.mapMessage} role="status">Loading the globe…</p>}
            <div className={styles.mapControls} role="group" aria-label="Globe controls">
                <button type="button" aria-label="Zoom in" onClick={() => changeZoom(1.2)} disabled={zoom >= maxZoom}><Plus size={18} /></button>
                <button type="button" aria-label="Zoom out" onClick={() => changeZoom(1 / 1.2)} disabled={zoom <= minZoom}><Minus size={18} /></button>
                <button type="button" aria-label="Reset globe view" onClick={onReset}><RotateCcw size={17} /></button>
            </div>
            <p className={styles.gestures}>Drag to rotate <span>·</span> Scroll to zoom</p>
        </section>
    )
}

// Types for the subset of react-simple-maps used by this application.
declare module 'react-simple-maps' {
    import type { ComponentType, CSSProperties, ReactNode, SVGProps } from 'react'
    import type { Feature, Geometry } from 'geojson'

    export type MapGeography = Feature<Geometry, {
        ISO_A3?: string
        ADM0_A3?: string
        ISO_A3_EH?: string
        NAME?: string
        name?: string
    }> & { rsmKey: string; svgPath: string }

    export const ComposableMap: ComponentType<SVGProps<SVGSVGElement> & {
        projectionConfig?: { scale?: number }
    }>
    export const Geographies: ComponentType<{
        geography: string
        children: (data: { geographies: MapGeography[] }) => ReactNode
    }>
    export const Geography: ComponentType<Omit<SVGProps<SVGPathElement>, 'style'> & {
        geography: MapGeography
        style?: { default?: CSSProperties; hover?: CSSProperties; pressed?: CSSProperties }
    }>
    export const ZoomableGroup: ComponentType<{
        children?: ReactNode
        center?: [number, number]
        zoom?: number
        minZoom?: number
        maxZoom?: number
        onMoveEnd?: (position: { coordinates: [number, number]; zoom: number }) => void
    }>
}

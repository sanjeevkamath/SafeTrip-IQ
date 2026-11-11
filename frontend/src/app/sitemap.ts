import type { MetadataRoute } from 'next'
import { listCountryScores } from '@/lib/server/queries'
import { isPreview, siteUrl } from '@/lib/site-metadata'

export const dynamic = 'force-dynamic'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
    if (isPreview) return []

    const countries = await listCountryScores()
    return [
        { url: `${siteUrl}/` },
        { url: `${siteUrl}/countries` },
        ...countries.map(({ iso3 }) => ({ url: `${siteUrl}/country/${iso3}` })),
    ]
}

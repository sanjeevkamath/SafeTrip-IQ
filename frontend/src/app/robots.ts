import type { MetadataRoute } from 'next'
import { isPreview, siteUrl } from '@/lib/site-metadata'

export default function robots(): MetadataRoute.Robots {
    return {
        rules: { userAgent: '*', disallow: '/api/' },
        sitemap: isPreview ? undefined : `${siteUrl}/sitemap.xml`,
    }
}

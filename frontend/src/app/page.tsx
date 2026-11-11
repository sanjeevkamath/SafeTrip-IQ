import { Analytics } from '@vercel/analytics/next'
import ExploreHome from '@/components/ExploreHome'
import { pageMetadata, siteName, siteUrl } from '@/lib/site-metadata'

export const metadata = pageMetadata(
    'SafeTrip IQ | Travel Advisories and Country Guides',
    'Explore the globe, compare travel safety scores, and find official travel advisories and trip essentials for your destination.',
    '/',
)

const website = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: siteName,
    url: `${siteUrl}/`,
}

export default function Home() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{
                __html: JSON.stringify(website).replace(/</g, '\\u003c'),
            }} />
            <ExploreHome />
            <Analytics />
        </>
    )
}

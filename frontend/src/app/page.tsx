import type { Metadata } from 'next'
import { Analytics } from '@vercel/analytics/next'
import ExploreHome from '@/components/ExploreHome'

export const metadata: Metadata = {
    title: 'SafeTrip IQ — Explore destinations',
    description: 'Explore destinations and check travel advice before you go.',
}

export default function Home() {
    return (
        <>
            <ExploreHome />
            <Analytics />
        </>
    )
}

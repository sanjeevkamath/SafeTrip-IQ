import type { Metadata } from 'next'

export const siteName = 'SafeTrip IQ'
export const siteUrl = new URL(process.env.SAFETRIP_SITE_URL || 'https://safetripiq.vercel.app').origin
export const isPreview = process.env.VERCEL_ENV === 'preview'

export function pageMetadata(title: string, description: string, path: string): Metadata {
    const images = [{
        url: '/brand/share.png',
        width: 1200,
        height: 630,
        alt: 'SafeTrip IQ compass logo and travel guides',
    }]

    return {
        title,
        description,
        alternates: { canonical: path },
        openGraph: {
            type: 'website',
            siteName,
            url: path,
            title,
            description,
            images,
        },
        twitter: { card: 'summary_large_image', title, description, images },
    }
}

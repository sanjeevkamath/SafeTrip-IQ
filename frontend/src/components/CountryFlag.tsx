'use client'

import { useState } from 'react'
import Image from 'next/image'

export default function CountryFlag({ flagUrl, fallbackUrl, iso2, width = 36, height = 24, className, fallbackClassName }: {
    flagUrl: string | null
    fallbackUrl?: string
    iso2: string | null
    width?: number
    height?: number
    className?: string
    fallbackClassName?: string
}) {
    const [failedUrls, setFailedUrls] = useState<string[]>([])
    const imageUrl = [flagUrl, fallbackUrl].find(url => url && !failedUrls.includes(url))
    if (imageUrl) {
        return <Image className={className} src={imageUrl} width={width} height={height} alt=""
            unoptimized onError={() => setFailedUrls(urls => [...urls, imageUrl])} />
    }
    const code = iso2?.toUpperCase()
    if (!code || !/^[A-Z]{2}$/.test(code)) return null
    const emoji = String.fromCodePoint(...Array.from(code, letter => 0x1f1e6 + letter.charCodeAt(0) - 65))
    return <span className={fallbackClassName} aria-hidden="true">{emoji}</span>
}

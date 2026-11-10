'use client'

import { useEffect, useState } from 'react'
import styles from './ExploreHome.module.css'

type RefreshData = {
    published_at: string | null
    overdue?: boolean
    score_published_at?: string | null
    score_overdue?: boolean
}

const timestampFormat = new Intl.DateTimeFormat('en', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    timeZone: 'UTC', timeZoneName: 'short',
})

export default function RefreshStatus() {
    const [data, setData] = useState<RefreshData | null>()
    useEffect(() => {
        const controller = new AbortController()
        fetch('/api/refresh-status', { cache: 'no-store', signal: controller.signal })
            .then(async response => {
                if (!response.ok) throw new Error('Refresh status unavailable')
                setData(await response.json())
            })
            .catch(() => {
                if (!controller.signal.aborted) setData(null)
            })
        return () => controller.abort()
    }, [])

    const latest = Math.max(...[data?.published_at, data?.score_published_at]
        .map(value => value ? Date.parse(value) : NaN).filter(Number.isFinite))
    const updatedAt = Number.isFinite(latest) ? new Date(latest) : null

    return (
        <footer className={styles.freshness} role="status">
            Last updated at: {updatedAt
                ? <time dateTime={updatedAt.toISOString()}>{timestampFormat.format(updatedAt)}</time>
                : data === undefined ? 'Checking…' : <span title="No recorded update timestamp">—</span>}
            {(data?.overdue || data?.score_overdue) && <span className={styles.overdue}> · refresh overdue</span>}
        </footer>
    )
}

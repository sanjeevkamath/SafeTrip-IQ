'use client'

import { useEffect, useState } from 'react'

export default function RefreshStatus() {
    const [message, setMessage] = useState('Checking advisory refresh time…')
    useEffect(() => {
        const controller = new AbortController()
        fetch('/api/refresh-status', { cache: 'no-store', signal: controller.signal })
            .then(async response => {
                if (!response.ok) throw new Error('Unavailable')
                const status = await response.json()
                if (!status) {
                    setMessage('Advisory refresh time is not yet available.')
                    return
                }
                const date = new Date(status.published_at)
                if (Number.isNaN(date.getTime())) throw new Error('Invalid date')
                const label = status.source_kind === 'state_department_feed' ? 'Advisories refreshed' :
                    status.source_kind === 'local_xml' ? 'Local XML data refreshed' : 'Data refreshed (source unverified)'
                setMessage(`${label}: ${date.toLocaleString()}.${status.overdue ? ' Last refresh was over 48 hours ago.' : ''}`)
            })
            .catch(() => {
                if (!controller.signal.aborted) setMessage('Advisory refresh time is temporarily unavailable.')
            })
        return () => controller.abort()
    }, [])
    return <p className="text-sm text-gray-600" role="status">{message}</p>
}

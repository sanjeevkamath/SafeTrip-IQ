'use client'

import Link from 'next/link'
import styles from '@/components/CountryGuide.module.css'
import palette from '@/components/AtlanticSand.module.css'

export default function CountryError({ reset }: { reset: () => void }) {
    return (
        <main className={`${palette.theme} ${styles.guide}`}>
            <div className={`${styles.shell} ${styles.error}`}>
                <Link href="/" className={styles.sourceLink}>← Back to globe</Link>
                <h1 className="text-2xl font-bold">Travel data is temporarily unavailable</h1>
                <button type="button" onClick={reset} className={styles.retry}>Try again</button>
            </div>
        </main>
    )
}

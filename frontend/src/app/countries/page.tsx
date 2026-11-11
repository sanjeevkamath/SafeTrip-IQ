import Link from 'next/link'
import BrandWordmark from '@/components/BrandWordmark'
import palette from '@/components/AtlanticSand.module.css'
import guideStyles from '@/components/CountryGuide.module.css'
import { listCountryScores } from '@/lib/server/queries'
import { pageMetadata, siteName } from '@/lib/site-metadata'
import styles from './directory.module.css'

export const dynamic = 'force-dynamic'

export const metadata = pageMetadata(
    `Country Travel Guides | ${siteName}`,
    'Browse travel safety guides by country, with official advisory links and trip essentials.',
    '/countries',
)

export default async function CountryDirectory() {
    const countries = await listCountryScores()
    countries.sort((a, b) => a.name.localeCompare(b.name, 'en'))

    return (
        <main className={`${palette.theme} ${guideStyles.guide}`}>
            <div className={guideStyles.shell}>
                <header className={guideStyles.header}>
                    <Link href="/" className={guideStyles.brand}><BrandWordmark /></Link>
                    <Link href="/" className={guideStyles.sourceLink}>← Globe</Link>
                </header>
                <h1 className={styles.title}>Country guides</h1>
                <ul className={styles.list} role="list">
                    {countries.map(({ iso3, name }) => (
                        <li key={iso3}><Link href={`/country/${iso3}`} prefetch={false}>{name}</Link></li>
                    ))}
                </ul>
            </div>
        </main>
    )
}

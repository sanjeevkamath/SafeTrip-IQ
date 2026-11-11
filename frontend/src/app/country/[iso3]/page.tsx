import Link from 'next/link'
import { notFound } from 'next/navigation'
import CountryFlag from '@/components/CountryFlag'
import OfficialAdvisories, { advisorySourceLink } from '@/components/OfficialAdvisories'
import SafetyScoreDetails from '@/components/SafetyScoreDetails'
import styles from '@/components/CountryGuide.module.css'
import palette from '@/components/AtlanticSand.module.css'
import { getGuideReference, guideItems, scorePresentation } from '@/lib/country-guide'
import { getCountryDetails, getCountryAdvisories } from '@/lib/server/queries'
import type { Culture } from '@/lib/server/types'

interface PageProps {
    params: Promise<{ iso3: string }>
}

export const dynamic = 'force-dynamic'

const ukAdviceDirectory = 'https://www.gov.uk/foreign-travel-advice'

function GuideLink({ href, children }: { href: string; children: string }) {
    return <a className={styles.sourceLink} href={href} target="_blank" rel="noopener noreferrer">
        {children} <span aria-hidden="true">→</span>
        <span className="sr-only"> (opens in a new tab)</span>
    </a>
}

function Fact({ label, value }: { label: string; value: string | null | undefined }) {
    return value?.trim() ? <div className={styles.fact}><dt>{label}</dt><dd>{value}</dd></div> : null
}

function LocalDetails({ culture, remainingNotes }: { culture: Culture; remainingNotes: string[] }) {
    const sections: [string, string[], ('green' | 'red')?][] = [
        ['Safety notes', remainingNotes],
        ['Local etiquette', guideItems(culture.etiquette)],
        ['Do', guideItems(culture.dos), 'green'],
        ['Avoid', guideItems(culture.donts), 'red'],
        ['Greetings', guideItems(culture.greeting, true)],
        ['Religion and beliefs', guideItems(culture.religion)],
        ['Food', guideItems(culture.food, true)],
        ['Cities', guideItems(culture.cities, true)],
    ]
    const seen = new Set<string>()
    const uniqueSections = sections.map(([name, items, tone]) => [name, items.filter(item => {
        const key = item.toLowerCase().replace(/[.?!]+$/, '')
        if (seen.has(key)) return false
        seen.add(key)
        return true
    }), tone] as const).filter(([, items]) => items.length)
    if (!uniqueSections.length) return null

    return <details className={styles.disclosure}>
        <summary>Local customs and places</summary>
        <div className={styles.detailBody}>
            {uniqueSections.map(([title, items, tone]) => <div key={title} data-tone={tone}>
                <h3>{title}</h3>
                <ul className={styles.list}>{items.map(item => <li key={item}>{item}</li>)}</ul>
            </div>)}
        </div>
    </details>
}

export default async function CountryPage({ params }: PageProps) {
    const { iso3 } = await params
    const details = await getCountryDetails(iso3)
    if (!details) notFound()

    const { country, score, culture } = details
    const reference = getGuideReference(country.iso3)
    const advisories = process.env.SAFETRIP_ADVISORIES_ENABLED === '1'
        ? await getCountryAdvisories(country.iso3).catch(() => null)
        : null
    const sources = advisories?.sources ?? null
    const importedUk = sources?.uk_fcdo.documents.find(document => document.coverage_scope === 'whole_country')
    const ukUrl = reference?.uk ?? (importedUk && advisorySourceLink(importedUk))
    const ukGuide = ukUrl?.match(/^https:\/\/www\.gov\.uk\/foreign-travel-advice\/[a-z0-9-]+(?=\/|\?|#|$)/)?.[0]
    const currency = culture?.currency?.trim() || reference?.currency
    const region = reference?.region ?? country.continent
    const overview = culture?.overview?.trim()
    const value = score?.safe_trip_score
    const shownScore = typeof value === 'number' && Number.isFinite(value) ? scorePresentation(value) : null
    const safetyNotes = guideItems(culture?.cultural_safety_notes)
    const highlightedNotes = reference?.tips ? [] : safetyNotes.slice(0, 3)
    const remainingNotes = safetyNotes.slice(highlightedNotes.length)

    return (
        <main className={`${palette.theme} ${styles.guide}`}>
            <div className={styles.shell}>
                <header className={styles.header}>
                    <Link href="/" className={styles.brand}>SafeTrip <span>IQ</span></Link>
                    <Link href="/" className={styles.sourceLink} aria-label="Back to globe">
                        <span aria-hidden="true">← </span><span className={styles.backFull}>Back to globe</span>
                        <span className={styles.backShort}>Globe</span>
                    </Link>
                </header>

                <div className={styles.hero}>
                    <div className={styles.country}>
                        {region && <p className={styles.region}>{region}</p>}
                        <div className={styles.name}>
                            <h1>{country.name}</h1>
                            <CountryFlag flagUrl={country.flag_url} fallbackUrl={reference?.flag}
                                iso2={country.iso2} width={43} height={29}
                                className={styles.flag} fallbackClassName={styles.flagEmoji} />
                        </div>
                    </div>
                    <dl className={styles.score}>
                        <dt>SafeTrip score</dt>
                        <dd>{shownScore ? <><strong data-tone={shownScore.tone}>{shownScore.label}</strong><span>/ 10</span></>
                            : 'Unavailable'}</dd>
                    </dl>
                    {overview && <p className={`${styles.overview} ${styles.muted}`}>{overview}</p>}
                </div>

                <div className={styles.columns}>
                    <OfficialAdvisories sources={sources} links={{
                        us_state: reference?.us,
                        uk_fcdo: ukGuide,
                    }} scoreUsLevel={score?.scoring_version === 'us-official-cluster-v1' ? score.official_us_level : undefined} />

                    <aside className={styles.essentials} aria-labelledby="trip-essentials-title">
                        <h2 id="trip-essentials-title">Trip essentials</h2>
                        {(currency || reference?.emergency || culture?.language) && <dl className={styles.facts}>
                            <Fact label="Currency" value={currency} />
                            <Fact label="Emergency" value={reference?.emergency} />
                            <Fact label="Language" value={culture?.language} />
                        </dl>}
                        <GuideLink href={ukGuide ? `${ukGuide}/getting-help` : ukAdviceDirectory}>
                            {ukGuide ? 'Getting help' : 'Find local help and emergency contacts'}
                        </GuideLink>
                    </aside>

                    <section className={styles.preparation} aria-labelledby="before-you-go-title">
                        <h2 id="before-you-go-title">Before you go</h2>
                        <div className={styles.tip}>
                            <h3>Passport and visa rules</h3>
                            <p>Check what applies to your nationality before you book.</p>
                            <GuideLink href={ukGuide ? `${ukGuide}/entry-requirements` : ukAdviceDirectory}>
                                {ukGuide ? 'Entry rules for UK passport holders' : 'Find entry requirements'}
                            </GuideLink>
                        </div>

                        {reference?.tips.map(tip => <div key={tip.title} className={styles.tip}>
                            <h3>{tip.title}</h3>
                            <p>{tip.body}</p>
                            {tip.source && <GuideLink href={tip.source.url}>{tip.source.label}</GuideLink>}
                        </div>)}

                        {highlightedNotes.length > 0 && <div className={styles.tip}>
                            <h3>Local safety notes</h3>
                            <ul className={`${styles.list} ${styles.muted}`}>
                                {highlightedNotes.map(note => <li key={note}>{note}</li>)}
                            </ul>
                        </div>}

                        {(culture || (score && shownScore)) && <div className={styles.more}>
                            {culture && <LocalDetails culture={culture} remainingNotes={remainingNotes} />}
                            {score && shownScore && <SafetyScoreDetails
                                bertScore={score.bert_score}
                                clusteringScore={score.clustering_score}
                                scoringVersion={score.scoring_version}
                                officialUSLevel={score.official_us_level}
                                officialUSComponent={score.official_us_component}
                                clusteringComponent={score.clustering_component}
                            />}
                        </div>}
                    </section>
                </div>
            </div>
        </main>
    )
}

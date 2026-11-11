import type { AdvisorySummary, WarningExcerpt } from '@/lib/server/types'
import styles from './CountryGuide.module.css'

type Source = AdvisorySummary['source']
type SourceData = { status: string; documents: AdvisorySummary[] }
type Props = {
    sources: Record<Source, SourceData> | null
    links?: Partial<Record<Source, string>>
    scoreUsLevel?: number | null
}

const sourceNames: Record<Source, string> = {
    us_state: 'US Department of State',
    uk_fcdo: 'UK Foreign Office',
}
const sourceDirectories: Record<Source, string> = {
    us_state: 'https://travel.state.gov/en/international-travel/travel-advisories.html',
    uk_fcdo: 'https://www.gov.uk/foreign-travel-advice',
}
const ukWarnings: Record<string, string> = {
    avoid_all_travel_to_whole_country: 'Against all travel throughout the destination',
    avoid_all_but_essential_travel_to_whole_country: 'Against all but essential travel throughout the destination',
    avoid_all_travel_to_parts: 'Against all travel to certain areas',
    avoid_all_but_essential_travel_to_parts: 'Against all but essential travel to certain areas',
}
const usLevels: Record<number, string> = {
    1: 'Exercise normal precautions', 2: 'Exercise increased caution',
    3: 'Reconsider travel', 4: 'Do not travel',
}

function date(value: string | null | undefined, includeTime = false) {
    if (!value) return null
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return null
    const formatted = parsed.toLocaleString('en-GB', {
        timeZone: 'UTC', dateStyle: 'medium', ...(includeTime ? { timeStyle: 'short' } : {}),
    })
    return includeTime ? formatted + ' UTC' : formatted
}

export function advisorySourceLink(document: AdvisorySummary) {
    try {
        const url = new URL(document.source_url)
        const host = document.source === 'us_state' ? 'travel.state.gov' : 'www.gov.uk'
        return url.protocol === 'https:' && url.hostname === host && !url.username && !url.password ? url.href : null
    } catch { return null }
}

function ukSeverity(flag: string) {
    if (flag.startsWith('avoid_all_travel_')) return 4
    if (flag.startsWith('avoid_all_but_essential_')) return 3
    return 0
}

function severity(document: AdvisorySummary) {
    return document.source === 'us_state' ? document.us_level ?? 0 :
        Math.max(0, ...(document.uk_alert_status ?? []).map(ukSeverity))
}

function AffectedAreas({ excerpts }: { excerpts: WarningExcerpt[] | null | undefined }) {
    if (!excerpts?.length) return <p className={styles.adviceBody}>Affected areas could not be listed here. Read the full UK advice for geographic limits and exceptions.</p>
    const groups: { warning: string; areas: { heading: string | null; paragraphs: WarningExcerpt[] }[] }[] = []
    for (const excerpt of excerpts) {
        let group = groups[groups.length - 1]
        if (!group || group.warning !== excerpt.warning_heading) {
            group = { warning: excerpt.warning_heading, areas: [] }
            groups.push(group)
        }
        let area = group.areas[group.areas.length - 1]
        if (!area || area.heading !== excerpt.heading) {
            area = { heading: excerpt.heading, paragraphs: [] }
            group.areas.push(area)
        }
        area.paragraphs.push(excerpt)
    }
    return <details className={styles.disclosure}>
        <summary>Affected areas</summary>
        <div className={styles.disclosureBody}>
            {groups.map((group, i) => <section key={i} className={styles.disclosureBody}>
                <h4>{group.warning}</h4>
                {group.areas.map((area, j) => <div key={j} className={styles.disclosureBody}>
                    {area.heading && area.heading !== group.warning && <h5>{area.heading}</h5>}
                    {area.paragraphs.map(p => <p key={`${p.section_slug}-${p.paragraph_index}`}>{p.body}</p>)}
                </div>)}
            </section>)}
        </div>
    </details>
}

function SourceLink({ source, url }: { source: Source; url: string }) {
    return <a className={styles.sourceLink} href={url} target="_blank" rel="noopener noreferrer">
        {source === 'us_state' ? 'Read US advisory' : 'Read UK travel advice'} <span aria-hidden="true">→</span>
        <span className="sr-only"> (opens in a new tab)</span>
    </a>
}

function AdvisoryRow({ document }: { document: AdvisorySummary }) {
    const { source, region_label: region, uk_alert_status: flags } = document
    const issued = document.source_public_updated_at ?? document.source_updated_at
    const issuedDate = date(issued)
    const link = advisorySourceLink(document)
    const warnings = flags && [...flags].sort((a, b) => ukSeverity(b) - ukSeverity(a))
        .map(flag => ukWarnings[flag] ?? 'Warning status requires review; read the source advice')
    const headline = source === 'us_state'
        ? document.us_level == null ? 'Advisory level not provided' : `Level ${document.us_level}: ${usLevels[document.us_level] ?? 'Read the source advice'}`
        : warnings?.[0] ?? (flags === null ? 'Warning status not provided' : 'No travel-restriction flags recorded')

    return <article className={styles.adviceRow}>
        <p className={styles.eyebrow}>{sourceNames[source]}{issuedDate && ` · ${issuedDate}`}</p>
        <h3 className={severity(document) >= 3 ? styles.priority : undefined}>{headline}</h3>
        {document.coverage_scope === 'parts' && <p className={styles.adviceBody}>
            {region ? `Regional advice: ${region}` : 'Applies to specific regions.'}
        </p>}
        {source === 'uk_fcdo' && <>
            {warnings && warnings.length > 1 && <ul className={styles.adviceBody}>{warnings.slice(1).map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
            {flags?.length === 0 && <p className={styles.adviceBody}>Other risks and guidance may still apply.</p>}
            {flags?.some(flag => flag.endsWith('_parts')) && <AffectedAreas excerpts={document.warning_excerpts} />}
        </>}
        <div className={styles.rowLinks}>
            {link && <SourceLink source={source} url={link} />}
            <details className={styles.disclosure}>
                <summary>Source dates</summary>
                <dl className={styles.disclosureBody}>
                    {date(issued, true) && <div><dt>Published or updated: </dt><dd>{date(issued, true)}</dd></div>}
                    {date(document.source_reviewed_at, true) && <div><dt>Reviewed: </dt><dd>{date(document.source_reviewed_at, true)}</dd></div>}
                    <div><dt>Retrieved: </dt><dd>{date(document.fetched_at, true) ?? 'Not provided'}</dd></div>
                </dl>
            </details>
        </div>
    </article>
}

export default function OfficialAdvisories({ sources, links = {}, scoreUsLevel }: Props) {
    const documents = [...(sources?.us_state.documents ?? []), ...(sources?.uk_fcdo.documents ?? [])]
        .sort((a, b) => severity(b) - severity(a))
    const missing = (['us_state', 'uk_fcdo'] as const).filter(source => !sources?.[source].documents.length)
    const showScoreWarning = scoreUsLevel === 4 && !sources?.us_state.documents.some(document =>
        document.coverage_scope === 'whole_country' && document.us_level != null)

    return <section className={styles.advice} aria-labelledby="official-advice-title">
        <h2 id="official-advice-title">Official travel advice</h2>
        {showScoreWarning && <article className={styles.adviceRow}>
            <p className={styles.eyebrow}>US advisory used in the SafeTrip score</p>
            <h3 className={styles.priority}>Level 4: Do not travel</h3>
            <SourceLink source="us_state" url={links.us_state ?? sourceDirectories.us_state} />
        </article>}
        {!sources && <p className={styles.muted} role="status">Imported advice is temporarily unavailable. Check the government sources for current guidance.</p>}
        {documents.map(document => <AdvisoryRow key={`${document.version_id}-${document.region_label ?? ''}`} document={document} />)}
        {missing.map(source => {
            if (source === 'us_state' && showScoreWarning && !sources?.us_state.documents.length) return null
            return <article key={source} className={styles.adviceRow}>
                <p className={styles.eyebrow}>{sourceNames[source]}</p>
                {sources && <p className={styles.adviceBody}>No imported advice is available from this source.</p>}
                <SourceLink source={source} url={links[source] ?? sourceDirectories[source]} />
            </article>
        })}
    </section>
}

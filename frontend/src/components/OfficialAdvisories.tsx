import type { AdvisorySummary, WarningExcerpt } from '@/lib/server/types'

type SourceData = { status: string; documents: AdvisorySummary[] }
type Props = { sources: { us_state: SourceData; uk_fcdo: SourceData } | null }
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
function date(value: string | null) {
    if (!value) return 'Not provided'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return 'Not provided'
    return parsed.toLocaleString('en-GB', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) + ' UTC'
}
function sourceLink(document: AdvisorySummary) {
    try {
        const url = new URL(document.source_url)
        const host = document.source === 'us_state' ? 'travel.state.gov' : 'www.gov.uk'
        return url.protocol === 'https:' && url.hostname === host && !url.username && !url.password ? url.href : null
    } catch { return null }
}

function AffectedAreas({ excerpts }: { excerpts: WarningExcerpt[] | null | undefined }) {
    if (!excerpts?.length) return <p className="text-sm text-gray-600 mt-3">Affected areas could not be listed here. Read the full UK advice for geographic limits and exceptions.</p>
    const groups: { warning: string; areas: { heading: string | null; paragraphs: WarningExcerpt[] }[] }[] = []
    for (const excerpt of excerpts) {
        let group = groups[groups.length - 1]
        if (!group || group.warning !== excerpt.warning_heading) {
            group = { warning: excerpt.warning_heading, areas: [] }; groups.push(group)
        }
        let area = group.areas[group.areas.length - 1]
        if (!area || area.heading !== excerpt.heading) {
            area = { heading: excerpt.heading, paragraphs: [] }; group.areas.push(area)
        }
        area.paragraphs.push(excerpt)
    }
    return <details className="mt-4 rounded-lg border border-slate-200 p-3">
        <summary className="cursor-pointer font-semibold text-indigo-700">Affected areas</summary>
        <p className="text-sm text-gray-600 mt-3">Official UK wording, including geographic limits and exceptions. This may include context about neighbouring areas.</p>
        <div className="mt-3 space-y-5">
            {groups.map((group, i) => <div key={i}>
                <h4 className="font-semibold text-gray-900">{group.warning}</h4>
                {group.areas.map((area, j) => <div key={j} className="mt-3 space-y-2">
                    {area.heading && area.heading !== group.warning && <h5 className="font-semibold text-gray-800">{area.heading}</h5>}
                    {area.paragraphs.map(p => <p key={`${p.section_slug}-${p.paragraph_index}`} className="text-sm leading-relaxed text-gray-700">{p.body}</p>)}
                </div>)}
            </div>)}
        </div>
    </details>
}

export default function OfficialAdvisories({ sources }: Props) {
    return <section aria-labelledby="official-advice-title" className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 sm:p-8 mb-8">
        <h2 id="official-advice-title" className="text-2xl font-bold text-gray-900 mb-2">Official travel advice</h2>
        <p className="text-gray-600 mb-6">US and UK guidance is shown separately. Regional warnings may differ; read the full source before travelling.</p>
        {!sources ? <p role="status" className="text-gray-600">Official advice is temporarily unavailable. Try again later.</p>
            : <div className="grid md:grid-cols-2 gap-6">
                {(['us_state', 'uk_fcdo'] as const).map(source => {
                    const documents = sources[source].documents
                    return <article key={source} className="border border-slate-200 rounded-xl p-5">
                        <h3 className="text-lg font-semibold text-gray-900 mb-3">{source === 'us_state' ? 'US Department of State' : 'UK Foreign, Commonwealth & Development Office'}</h3>
                        {!documents.length ? <p className="text-gray-600">No imported advice is available for this destination from this source. This does not indicate low risk.</p>
                            : <>
                                {documents.length > 1 && <p className="text-sm text-gray-600 mb-3">Multiple source documents apply. Their warnings are shown individually.</p>}
                                {documents.map(document => {
                                    const href = sourceLink(document)
                                    return <div key={`${document.version_id}-${document.region_label ?? ''}`} className="border-t border-slate-100 pt-4 mt-4 first:border-0 first:pt-0 first:mt-0">
                                        {document.coverage_scope === 'parts' && <p className="font-semibold text-gray-800 mb-2">Regional advice: {document.region_label}</p>}
                                        {source === 'us_state' ? <p className="font-semibold text-gray-900">{document.us_level === null ? 'Advisory level not provided' : `Level ${document.us_level}: ${usLevels[document.us_level] ?? 'Read the source advice'}`}</p>
                                            : document.uk_alert_status === null ? <p className="text-gray-900">Warning status not provided. Read the source advice.</p>
                                                : document.uk_alert_status.length ? <ul className="list-disc pl-5 text-gray-900 space-y-2">{document.uk_alert_status.map(flag => <li key={flag}>{ukWarnings[flag] ?? 'Warning status requires review; read the source advice'}</li>)}</ul>
                                                : <p className="text-gray-900">No travel-restriction flags recorded. Other risks and guidance may still apply.</p>}
                                        {source === 'uk_fcdo' && document.uk_alert_status?.some(flag => flag.endsWith('_parts')) && <AffectedAreas excerpts={document.warning_excerpts} />}
                                        <dl className="text-sm text-gray-600 mt-3 space-y-1">
                                            <div><dt className="inline font-medium">Source published/updated: </dt><dd className="inline">{date(document.source_public_updated_at ?? document.source_updated_at)}</dd></div>
                                            {document.source_reviewed_at && <div><dt className="inline font-medium">Source reviewed: </dt><dd className="inline">{date(document.source_reviewed_at)}</dd></div>}
                                            <div><dt className="inline font-medium">Retrieved: </dt><dd className="inline">{date(document.fetched_at)}</dd></div>
                                        </dl>
                                        {href && <a href={href} target="_blank" rel="noopener noreferrer" className="inline-block mt-3 text-indigo-700 underline underline-offset-2">Read full {source === 'us_state' ? 'US' : 'UK'} advice<span className="sr-only"> (opens in a new tab)</span></a>}
                                    </div>
                                })}
                            </>}
                    </article>
                })}
            </div>}
    </section>
}

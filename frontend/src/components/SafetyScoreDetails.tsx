import styles from './CountryGuide.module.css'

interface SafetyScoreDetailsProps {
    bertScore: number | null
    clusteringScore: number | null
    scoringVersion?: string | null
    officialUSLevel?: number | null
    officialUSComponent?: number | null
    clusteringComponent?: number | null
}

export default function SafetyScoreDetails({ bertScore, clusteringScore, scoringVersion,
    officialUSLevel, officialUSComponent, clusteringComponent }: SafetyScoreDetailsProps) {
    const official = scoringVersion === 'us-official-cluster-v1'
    const legacy = !scoringVersion || scoringVersion === 'legacy-v1'
    const rows: [string, string][] = []
    if (official && officialUSComponent != null) rows.push([
        officialUSLevel == null ? 'Official US advisory' : `Official US advisory — Level ${officialUSLevel}`,
        `${officialUSComponent.toFixed(2)} / 10`,
    ])
    if (official && clusteringComponent != null) rows.push([
        'Destination risk component',
        `${clusteringComponent.toFixed(2)} / 10${clusteringScore == null ? '' : ` · tier ${clusteringScore}`}`,
    ])
    if (legacy && bertScore != null) rows.push(['BERT Score', String(bertScore)])
    if (legacy && clusteringScore != null) rows.push(['Clustering Score', String(clusteringScore)])

    return <details className={styles.disclosure}>
        <summary>Score Breakdown</summary>
        <div className={styles.disclosureBody}>
            <p>The SafeTrip score is a countrywide index. Check official advice for regional warnings.</p>
            {!official && !legacy && <p>Score methodology is temporarily unavailable.</p>}
            {rows.length > 0 && <dl>
                {rows.map(([label, value]) => <div key={label}><dt>{label}: </dt><dd>{value}</dd></div>)}
            </dl>}
            {official && rows.length > 0 && <p>{rows.length === 1
                ? 'Based on one available component.'
                : 'Equal-weight average of the two components.'}</p>}
        </div>
    </details>
}

type GuideTip = {
    title: string
    body: string
    source?: { label: string; url: string }
}

type GuideReference = {
    region: string
    currency: string
    emergency: string
    flag: string
    uk: string
    us: string
    tips: GuideTip[]
}

// Country-specific practical information from the linked government guides.
const references: Partial<Record<string, GuideReference>> = {
    MAR: {
        region: 'North Africa',
        currency: 'Moroccan dirham (MAD)',
        emergency: 'Police 190 · Ambulance / fire 150',
        flag: '/flags/ma.svg',
        uk: 'https://www.gov.uk/foreign-travel-advice/morocco',
        us: 'https://travel.state.gov/en/international-travel/travel-advisories/morocco.html',
        tips: [
            {
                title: 'Carry some cash',
                body: 'Small businesses may only accept cash. Keep your exchange receipts if you plan to convert leftover dirhams.',
            },
            {
                title: 'Ask before taking photos',
                body: 'Ask permission before photographing people. Photography near sensitive military or political sites is illegal.',
                source: {
                    label: 'Local laws and customs',
                    url: 'https://www.gov.uk/foreign-travel-advice/morocco/safety-and-security#photography-and-filming',
                },
            },
        ],
    },
    PRT: {
        region: 'Southern Europe',
        currency: 'Euro (EUR)',
        emergency: '112 · Police, fire, ambulance',
        flag: '/flags/pt.svg',
        uk: 'https://www.gov.uk/foreign-travel-advice/portugal',
        us: 'https://travel.state.gov/en/international-travel/travel-advisories/portugal.html',
        tips: [{
            title: 'Secure valuables on crowded transport',
            body: 'Keep your passport and money close on busy trams and at stops, where distraction theft can occur.',
            source: {
                label: 'UK safety advice',
                url: 'https://www.gov.uk/foreign-travel-advice/portugal/safety-and-security#crime',
            },
        }],
    },
}

export function getGuideReference(iso3: string) {
    return references[iso3]
}

export function guideItems(value: string | null | undefined, commaSeparated = false): string[] {
    if (!value) return []
    let parsed: unknown = value
    try { parsed = JSON.parse(value) } catch { /* Older catalogue rows store plain text. */ }

    const items = Array.isArray(parsed) ? parsed :
        typeof parsed === 'string' ? parsed.split(commaSeparated ? /[;,]/ : /[;\n]/) : []

    return [...new Set(items.filter((item): item is string => typeof item === 'string')
        .map(item => item.trim()).filter(Boolean))]
}

export function scorePresentation(value: number) {
    const tone = value > 7 ? 'green' : value > 5 ? 'yellow' : 'red'
    const rounded = value.toFixed(1)
    // Keep the displayed number on the same side of a cutoff as its color.
    const crossesCutoff = (value > 7 && Number(rounded) <= 7) || (value > 5 && Number(rounded) <= 5)
    return { tone, label: crossesCutoff ? value.toFixed(2) : rounded }
}

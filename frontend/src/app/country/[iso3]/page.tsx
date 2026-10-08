import { getCountryDetails } from '@/lib/server/queries'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import SafetyScoreDetails from '@/components/SafetyScoreDetails'

interface PageProps {
    params: Promise<{
        iso3: string
    }>
}

export default async function CountryPage({ params }: PageProps) {
    const { iso3 } = await params

    const details = await getCountryDetails(iso3)
    if (!details) notFound()
    const { country, score, culture } = details

    // Helper function to safely parse fields that might be JSON arrays or plain strings
    const parseField = (field: string | null | undefined): string[] => {
        if (!field) return []

        try {
            const parsed = JSON.parse(field)

            if (Array.isArray(parsed)) {
                return parsed
            }

            if (typeof parsed === 'string') {
                // Check for semicolons first as they are a stronger delimiter in this dataset
                if (parsed.includes(';')) {
                    return parsed.split(';').map(s => s.trim()).filter(s => s.length > 0)
                }
                // Fallback to comma splitting
                return parsed.split(',').map(s => s.trim()).filter(s => s.length > 0)
            }

            return [String(parsed)]
        } catch {
            // If parsing fails, treat as plain string
            if (field.includes(';')) {
                return field.split(';').map(s => s.trim()).filter(s => s.length > 0)
            }
            // If no semicolons, check for commas but be careful purely splitting by comma can be risky for some text, 
            // but consistent with previous behavior for lists.
            // Ideally we only split if it looks like a list. 
            // For now, let's keep the semicolon check as the primary fix and comma as secondary.
            return field.split(',').map(s => s.trim()).filter(s => s.length > 0)
        }
    }

    // Parse JSON fields
    const greetings = parseField(culture?.greeting)
    const cities = parseField(culture?.cities)
    const etiquette = parseField(culture?.etiquette)
    const religion = parseField(culture?.religion)
    const dos = parseField(culture?.dos)
    const donts = parseField(culture?.donts)
    const food = parseField(culture?.food)
    const safetyNotes = parseField(culture?.cultural_safety_notes)

    const getScoreColor = (score: number) => {
        if (score >= 7) return 'bg-green-500'
        if (score >= 4) return 'bg-yellow-500'
        return 'bg-red-500'
    }

    const getScoreTextColor = (score: number) => {
        if (score >= 7) return 'text-green-600'
        if (score >= 4) return 'text-yellow-600'
        return 'text-red-600'
    }

    return (
        <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <Link href="/" className="inline-flex items-center gap-2 text-indigo-600 hover:text-indigo-700 font-medium mb-8 transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    Back to Search
                </Link>

                {/* Hero Section */}
                <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8 overflow-hidden relative">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-full blur-3xl opacity-30 -mr-32 -mt-32"></div>
                    <div className="relative">
                        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
                            <div className="flex items-start gap-4">
                                {country.flag_url && (
                                    <img
                                        src={country.flag_url}
                                        alt={`Flag of ${country.name}`}
                                        className="w-20 h-auto shadow-md rounded-lg border-2 border-white"
                                    />
                                )}
                                <div>
                                    <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-2">
                                        {country.name}
                                    </h1>
                                    <p className="text-gray-600 font-medium">{country.continent} • {country.iso3}</p>
                                </div>
                            </div>

                            {score && score.safe_trip_score !== null && (
                                <div className="bg-gradient-to-br from-white to-gray-50 p-6 rounded-xl border-2 border-gray-100 shadow-sm">
                                    <p className="text-sm font-semibold text-gray-600 mb-2">Safety Score</p>
                                    <div className="flex items-end gap-2">
                                        <span className={`text-5xl font-bold ${getScoreTextColor(score.safe_trip_score)}`}>
                                            {score.safe_trip_score?.toFixed(1)}
                                        </span>
                                        <span className="text-2xl text-gray-400 mb-1">/ 10</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                                        <div
                                            className={`h-2 rounded-full ${getScoreColor(score.safe_trip_score)} transition-all duration-500`}
                                            style={{ width: `${(score.safe_trip_score / 10) * 100}%` }}
                                        ></div>
                                    </div>
                                    <SafetyScoreDetails
                                        bertScore={score.bert_score}
                                        clusteringScore={score.clustering_score}
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {culture && (
                    <>
                        {/* Overview Section */}
                        {culture.overview && (
                            <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl shadow-lg p-8 mb-8 text-white">
                                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    Overview
                                </h2>
                                <p className="text-lg leading-relaxed text-indigo-50">{culture.overview}</p>
                            </div>
                        )}

                        {/* Quick Facts Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                            {culture.language && (
                                <div className="bg-white rounded-xl shadow-md p-6 border border-blue-100 hover:shadow-lg transition-shadow">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
                                            </svg>
                                        </div>
                                        <h3 className="text-lg font-semibold text-gray-800">Language</h3>
                                    </div>
                                    <p className="text-gray-600">{culture.language}</p>
                                </div>
                            )}

                            {culture.currency && (
                                <div className="bg-white rounded-xl shadow-md p-6 border border-green-100 hover:shadow-lg transition-shadow">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                                            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        </div>
                                        <h3 className="text-lg font-semibold text-gray-800">Currency</h3>
                                    </div>
                                    <p className="text-gray-600">{culture.currency}</p>
                                </div>
                            )}

                            {greetings.length > 0 && (
                                <div className="bg-white rounded-xl shadow-md p-6 border border-purple-100 hover:shadow-lg transition-shadow">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                                            <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                                            </svg>
                                        </div>
                                        <h3 className="text-lg font-semibold text-gray-800">Greetings</h3>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {greetings.map((greeting: string, idx: number) => (
                                            <span key={idx} className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm font-medium">
                                                {greeting}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                        {/* Safety Notes */}
                        {safetyNotes.length > 0 && (
                            <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-2xl shadow-lg border-2 border-amber-200 p-8 mb-8">
                                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-amber-800">
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                    </svg>
                                    Cultural Safety Notes
                                </h2>
                                <ul className="space-y-3">
                                    {safetyNotes.map((note: string, idx: number) => (
                                        <li key={idx} className="flex items-start gap-3 bg-white bg-opacity-60 p-4 rounded-lg">
                                            <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                            </svg>
                                            <span className="text-gray-800">{note}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                        )}

                        {/* Etiquette & Customs */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                            {/* Do&apos;s */}
                            {dos.length > 0 && (
                                <div className="bg-white rounded-2xl shadow-lg border-2 border-green-200 p-8">
                                    <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-green-700">
                                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        Do&apos;s
                                    </h2>
                                    <ul className="space-y-3">
                                        {dos.map((item: string, idx: number) => (
                                            <li key={idx} className="flex items-start gap-3">
                                                <svg className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                </svg>
                                                <span className="text-gray-700">{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Don'ts */}
                            {donts.length > 0 && (
                                <div className="bg-white rounded-2xl shadow-lg border-2 border-red-200 p-8">
                                    <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-red-700">
                                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        Don&apos;ts
                                    </h2>
                                    <ul className="space-y-3">
                                        {donts.map((item: string, idx: number) => (
                                            <li key={idx} className="flex items-start gap-3">
                                                <svg className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                </svg>
                                                <span className="text-gray-700">{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>

                        {/* General Etiquette */}
                        {etiquette.length > 0 && (
                            <div className="bg-white rounded-2xl shadow-lg border border-blue-100 p-8 mb-8">
                                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-gray-800">
                                    <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    Cultural Etiquette
                                </h2>
                                <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {etiquette.map((item: string, idx: number) => (
                                        <li key={idx} className="flex items-start gap-3 bg-blue-50 p-4 rounded-lg">
                                            <svg className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            <span className="text-gray-700">{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Religion & Food */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                            {/* Religion */}
                            {religion.length > 0 && (
                                <div className="bg-white rounded-2xl shadow-lg border border-amber-100 p-8">
                                    <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-gray-800">
                                        <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                        </svg>
                                        Religion & Beliefs
                                    </h2>
                                    <ul className="space-y-2">
                                        {religion.map((item: string, idx: number) => (
                                            <li key={idx} className="flex items-start gap-3">
                                                <span className="w-2 h-2 bg-amber-500 rounded-full mt-2 flex-shrink-0"></span>
                                                <span className="text-gray-700">{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Food */}
                            {food.length > 0 && (
                                <div className="bg-white rounded-2xl shadow-lg border border-orange-100 p-8">
                                    <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-gray-800">
                                        <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                                        </svg>
                                        Local Cuisine
                                    </h2>
                                    <div className="flex flex-wrap gap-3">
                                        {food.map((item: string, idx: number) => (
                                            <div key={idx} className="bg-gradient-to-br from-orange-50 to-red-50 border border-orange-200 rounded-xl px-4 py-3 hover:shadow-md transition-shadow">
                                                <p className="font-semibold text-orange-700">{item}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>



                        {/* Cities Section */}
                        {cities.length > 0 && (
                            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8">
                                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-gray-800">
                                    <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                                    </svg>
                                    Popular Cities
                                </h2>
                                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                                    {cities.map((city: string, idx: number) => (
                                        <div key={idx} className="bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-200 rounded-lg p-4 text-center hover:shadow-md transition-shadow">
                                            <p className="font-semibold text-indigo-700">{city}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                    </>
                )}

                {!culture && (
                    <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-12 text-center">
                        <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <p className="text-gray-500 text-lg">Cultural information not yet available for this country.</p>
                    </div>
                )}
            </div>
        </main>
    )
}

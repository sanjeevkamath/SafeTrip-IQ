import { supabase } from '@/lib/supabaseClient'
import Link from 'next/link'
import { notFound } from 'next/navigation'

interface PageProps {
    params: {
        iso3: string
    }
}

export default async function CountryPage({ params }: PageProps) {
    const { iso3 } = await params

    // Fetch country data
    const { data: country, error: countryError } = await supabase
        .from('countries')
        .select('*')
        .eq('iso3', iso3)
        .single()

    if (countryError || !country) {
        notFound()
    }

    // Fetch score data
    const { data: score, error: scoreError } = await supabase
        .from('scores')
        .select('*')
        .eq('iso3', iso3)
        .single()

    return (
        <main className="flex min-h-screen flex-col items-center p-24 bg-white text-black">
            <div className="max-w-4xl w-full">
                <Link href="/" className="text-blue-500 hover:underline mb-8 inline-block">
                    &larr; Back to Search
                </Link>

                <div className="bg-gray-50 p-8 rounded-xl shadow-sm border border-gray-100">
                    <div className="flex items-center gap-4 mb-6">
                        {country.flag_url && (
                            <img
                                src={country.flag_url}
                                alt={`Flag of ${country.name}`}
                                className="w-16 h-auto shadow-sm rounded-sm"
                            />
                        )}
                        <div>
                            <h1 className="text-4xl font-bold">{country.name}</h1>
                            <p className="text-gray-500">{country.continent} • {country.iso3}</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="bg-white p-6 rounded-lg border border-gray-200">
                            <h2 className="text-lg font-semibold mb-2">Safety Score</h2>
                            {score ? (
                                <div className="flex items-end gap-2">
                                    <span className={`text-5xl font-bold ${score.safe_trip_score >= 7 ? 'text-green-600' :
                                        score.safe_trip_score >= 4 ? 'text-yellow-600' :
                                            'text-red-600'
                                        }`}>
                                        {score.safe_trip_score?.toFixed(1) || 'N/A'}
                                    </span>
                                    <span className="text-gray-400 mb-2">/ 10</span>
                                </div>
                            ) : (
                                <p className="text-gray-500">No score available</p>
                            )}
                        </div>

                        <div className="bg-white p-6 rounded-lg border border-gray-200">
                            <h2 className="text-lg font-semibold mb-2">Details</h2>
                            <p className="text-gray-600">More cultural and safety details coming soon.</p>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    )
}

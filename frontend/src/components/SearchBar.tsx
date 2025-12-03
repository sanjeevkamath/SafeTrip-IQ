'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Search } from 'lucide-react'

type SearchResult = {
    iso3: string
    name: string
    continent: string | null
    flag_url: string | null
    safe_trip_score: number | null
}

export default function SearchBar() {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState<SearchResult[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const dropdownRef = useRef<HTMLDivElement>(null)
    const router = useRouter()

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            if (query.length >= 2) {
                fetchResults(query)
            } else {
                setResults([])
            }
        }, 300)

        return () => clearTimeout(timer)
    }, [query])

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const fetchResults = async (searchQuery: string) => {
        setIsLoading(true)
        try {
            const res = await fetch(`/api/search?query=${encodeURIComponent(searchQuery)}`)
            if (res.ok) {
                const data = await res.json()
                setResults(data)
                setShowDropdown(true)
            }
        } catch (error) {
            console.error('Search error:', error)
        } finally {
            setIsLoading(false)
        }
    }

    const handleSelect = (iso3: string) => {
        router.push(`/country/${iso3}`)
        setShowDropdown(false)
        setQuery('')
    }

    return (
        <div className="relative w-full max-w-md mx-auto" ref={dropdownRef}>
            <div className="relative">
                <input
                    type="text"
                    className="w-full px-4 py-2 pl-10 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
                    placeholder="Search for a country..."
                    value={query}
                    onChange={(e) => {
                        setQuery(e.target.value)
                        if (e.target.value.length < 2) setShowDropdown(false)
                    }}
                    onFocus={() => {
                        if (results.length > 0) setShowDropdown(true)
                    }}
                />
                <Search className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
                {isLoading && (
                    <div className="absolute right-3 top-2.5">
                        <div className="animate-spin h-5 w-5 border-2 border-blue-500 rounded-full border-t-transparent"></div>
                    </div>
                )}
            </div>

            {showDropdown && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {results.length > 0 ? (
                        <ul>
                            {results.map((result) => (
                                <li
                                    key={result.iso3}
                                    className="px-4 py-2 hover:bg-gray-100 cursor-pointer flex justify-between items-center text-black"
                                    onClick={() => handleSelect(result.iso3)}
                                >
                                    <div className="flex items-center gap-3">
                                        {result.flag_url && (
                                            <img
                                                src={result.flag_url}
                                                alt={`${result.name} flag`}
                                                className="w-8 h-6 object-cover rounded shadow-sm border border-gray-100"
                                            />
                                        )}
                                        <div>
                                            <div className="font-medium">{result.name}</div>
                                            {result.continent && (
                                                <div className="text-xs text-gray-500">{result.continent}</div>
                                            )}
                                        </div>
                                    </div>
                                    {result.safe_trip_score !== null && (
                                        <span className={`text-xs px-2 py-1 rounded-full ${result.safe_trip_score >= 7 ? 'bg-green-100 text-green-800' :
                                            result.safe_trip_score >= 4 ? 'bg-yellow-100 text-yellow-800' :
                                                'bg-red-100 text-red-800'
                                            }`}>
                                            {result.safe_trip_score.toFixed(1)}
                                        </span>
                                    )}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="px-4 py-2 text-gray-500">No results found</div>
                    )}
                </div>
            )}
        </div>
    )
}

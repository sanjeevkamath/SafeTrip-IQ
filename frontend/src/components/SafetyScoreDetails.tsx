'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, BarChart2, Hash } from 'lucide-react'

interface SafetyScoreDetailsProps {
    bertScore: number | null
    clusteringScore: number | null
}

export default function SafetyScoreDetails({ bertScore, clusteringScore }: SafetyScoreDetailsProps) {
    const [isOpen, setIsOpen] = useState(false)

    const getBertDetails = (score: number) => {
        if (score === 0) return { color: 'text-green-600', bg: 'bg-green-50' }
        if (score === 1) return { color: 'text-yellow-600', bg: 'bg-yellow-50' }
        if (score === 2) return { color: 'text-orange-600', bg: 'bg-orange-50' }
        return { color: 'text-red-600', bg: 'bg-red-50' }
    }

    const getClusteringDetails = (score: number) => {
        if (score <= 1) return { color: 'text-green-600', bg: 'bg-green-50' }
        if (score === 2) return { color: 'text-yellow-600', bg: 'bg-yellow-50' }
        if (score === 3) return { color: 'text-orange-600', bg: 'bg-orange-50' }
        return { color: 'text-red-600', bg: 'bg-red-50' }
    }

    if (bertScore === null && clusteringScore === null) return null

    return (
        <div className="mt-4 border-t border-gray-100 pt-4">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-between w-full text-sm font-medium text-gray-500 hover:text-indigo-600 transition-colors group"
            >
                <span>Score Breakdown</span>
                {isOpen ? (
                    <ChevronUp className="w-4 h-4 text-gray-400 group-hover:text-indigo-600 transition-colors" />
                ) : (
                    <ChevronDown className="w-4 h-4 text-gray-400 group-hover:text-indigo-600 transition-colors" />
                )}
            </button>

            {/* details */}
            <div
                className={`grid gap-3 overflow-hidden transition-all duration-300 ease-in-out ${isOpen ? 'mt-4 opacity-100 max-h-40' : 'max-h-0 opacity-0'
                    }`}
            >
                {bertScore !== null && (
                    <div className="flex items-center justify-between bg-white bg-opacity-60 p-3 rounded-lg border border-gray-100 shadow-sm">
                        <div className="flex items-center gap-2 pr-4">
                            <div className={`p-1.5 rounded-md ${getBertDetails(bertScore).bg}`}>
                                <BarChart2 className={`w-4 h-4 ${getBertDetails(bertScore).color}`} />
                            </div>
                            <span className="text-sm font-medium text-gray-700">BERT Score</span>
                        </div>
                        <span className={`text-sm font-bold ${getBertDetails(bertScore).color}`}>{bertScore}</span>
                    </div>
                )}

                {clusteringScore !== null && (
                    <div className="flex items-center justify-between bg-white bg-opacity-60 p-3 rounded-lg border border-gray-100 shadow-sm">
                        <div className="flex items-center gap-2 pr-4">
                            <div className={`p-1.5 rounded-md ${getClusteringDetails(clusteringScore).bg}`}>
                                <Hash className={`w-4 h-4 ${getClusteringDetails(clusteringScore).color}`} />
                            </div>
                            <span className="text-sm font-medium text-gray-700">Clustering Score</span>
                        </div>
                        <span className={`text-sm font-bold ${getClusteringDetails(clusteringScore).color}`}>{clusteringScore}</span>
                    </div>
                )}
            </div>
        </div>
    )
}

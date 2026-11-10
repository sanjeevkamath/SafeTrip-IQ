'use client'

import { useEffect, useId, useState, type KeyboardEvent } from 'react'
import { Search } from 'lucide-react'
import type { Destination } from '@/lib/explore'
import styles from './ExploreHome.module.css'

type SearchResponse = { query: string; results: Destination[]; failed?: boolean }

export default function SearchBar({ onSelect, onOpenChange }: {
    onSelect: (destination: Destination) => void
    onOpenChange: (open: boolean) => void
}) {
    const listId = useId()
    const [query, setQuery] = useState('')
    const [focused, setFocused] = useState(false)
    const [response, setResponse] = useState<SearchResponse>()
    const [activeIndex, setActiveIndex] = useState(-1)
    const term = query.trim()
    const expanded = focused && term.length >= 2
    const current = response?.query === term ? response : undefined
    const results = current?.results ?? []

    useEffect(() => {
        onOpenChange(expanded)
    }, [expanded, onOpenChange])

    useEffect(() => {
        if (term.length < 2) return
        const controller = new AbortController()
        const timer = window.setTimeout(async () => {
            try {
                const response = await fetch(`/api/search?query=${encodeURIComponent(term)}`, { signal: controller.signal })
                if (!response.ok) throw new Error('Search unavailable')
                const results: Destination[] = await response.json()
                if (!controller.signal.aborted) setResponse({ query: term, results })
            } catch {
                if (!controller.signal.aborted) setResponse({ query: term, results: [], failed: true })
            }
        }, 250)
        return () => {
            window.clearTimeout(timer)
            controller.abort()
        }
    }, [term])

    function clear() {
        setQuery('')
        setResponse(undefined)
        setActiveIndex(-1)
    }

    function select(destination: Destination) {
        clear()
        setFocused(false)
        onSelect(destination)
    }

    function handleKey(event: KeyboardEvent<HTMLInputElement>) {
        if (event.key === 'Escape' && expanded) {
            event.preventDefault()
            setFocused(false)
            setActiveIndex(-1)
        } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && results.length) {
            event.preventDefault()
            setFocused(true)
            const step = event.key === 'ArrowDown' ? 1 : -1
            setActiveIndex(index => index < 0 && step < 0 ? results.length - 1 : (index + step + results.length) % results.length)
        } else if (event.key === 'Enter' && expanded && results[activeIndex]) {
            event.preventDefault()
            select(results[activeIndex])
        }
    }

    return (
        <div className={styles.search} onBlur={event => {
            if (!event.currentTarget.contains(event.relatedTarget)) {
                setFocused(false)
                setActiveIndex(-1)
            }
        }}>
            <label className={styles.searchField}>
                <input
                    type="search"
                    role="combobox"
                    aria-label="Search a country"
                    aria-autocomplete="list"
                    aria-expanded={expanded}
                    aria-controls={expanded ? listId : undefined}
                    aria-activedescendant={expanded && results[activeIndex] ? `${listId}-${activeIndex}` : undefined}
                    placeholder="Search a country"
                    value={query}
                    onChange={event => {
                        setQuery(event.target.value)
                        setFocused(true)
                        setActiveIndex(-1)
                    }}
                    onFocus={() => setFocused(true)}
                    onKeyDown={handleKey}
                />
                <Search size={17} aria-hidden="true" />
            </label>
            {expanded && <div className={styles.searchResults}>
                <div id={listId} role="listbox" aria-label="Countries">
                    {results.map((destination, index) =>
                        <button key={destination.iso3} id={`${listId}-${index}`}
                            role="option" aria-selected={index === activeIndex} type="button"
                            className={styles.searchResult} tabIndex={-1}
                            onClick={() => select(destination)}
                        >
                            <span><strong>{destination.name}</strong>
                                {destination.continent && <small>{destination.continent}</small>}
                            </span>
                            <span className={styles.resultScore}>
                                {destination.safe_trip_score == null ? <small>Score unavailable</small> :
                                    <><strong>{destination.safe_trip_score.toFixed(1)} / 10</strong><small>SafeTrip score</small></>}
                            </span>
                        </button>
                    )}
                </div>
                {!current && <p role="status">Searching…</p>}
                {current?.failed && <p role="alert">Search is temporarily unavailable. Try again.</p>}
                {current && !current.failed && !results.length && <p role="status">No countries found.</p>}
                <button type="button" onClick={clear} className={styles.textAction}>Clear search</button>
            </div>}
        </div>
    )
}

'use client'

export default function CountryError({ reset }: { reset: () => void }) {
    return (
        <main className="p-8 text-center">
            <h1 className="text-2xl font-bold">Travel data is temporarily unavailable</h1>
            <p className="my-4">Please try again in a moment.</p>
            <button onClick={reset} className="rounded bg-blue-600 px-4 py-2 text-white">Try again</button>
        </main>
    )
}

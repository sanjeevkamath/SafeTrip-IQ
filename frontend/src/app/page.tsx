import SearchBar from '@/components/SearchBar'
import WorldMap from '@/components/WorldMap'

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gradient-to-b from-blue-50 to-white">
      <div className="z-10 max-w-7xl w-full items-center justify-center font-mono text-sm flex flex-col gap-8">
        <div className="text-center space-y-4">
          <h1 className="text-6xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-teal-500">
            SafeTrip IQ
          </h1>
          <p className="text-xl text-gray-600">
            Your intelligent companion for safe and culturally aware travel.
          </p>
        </div>

        <div className="w-full flex justify-center">
          <SearchBar />
        </div>

        <div className="mt-8 w-full bg-white rounded-xl shadow-lg p-6">
          <WorldMap />
        </div>
      </div>
    </main>
  )
}

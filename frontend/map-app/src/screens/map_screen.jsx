import React, { useState } from "react";
import { Info, X } from "lucide-react";

// Sample country data - replace with your actual data
const countryData = {
  USA: {
    name: "United States",
    color: "#3b82f6",
    info: "Population: 331 million. Capital: Washington, D.C.",
  },
  CAN: {
    name: "Canada",
    color: "#ef4444",
    info: "Population: 38 million. Capital: Ottawa.",
  },
  MEX: {
    name: "Mexico",
    color: "#10b981",
    info: "Population: 128 million. Capital: Mexico City.",
  },
  BRA: {
    name: "Brazil",
    color: "#f59e0b",
    info: "Population: 213 million. Capital: Brasília.",
  },
  GBR: {
    name: "United Kingdom",
    color: "#8b5cf6",
    info: "Population: 67 million. Capital: London.",
  },
  FRA: {
    name: "France",
    color: "#ec4899",
    info: "Population: 67 million. Capital: Paris.",
  },
  DEU: {
    name: "Germany",
    color: "#06b6d4",
    info: "Population: 83 million. Capital: Berlin.",
  },
  CHN: {
    name: "China",
    color: "#f97316",
    info: "Population: 1.4 billion. Capital: Beijing.",
  },
  IND: {
    name: "India",
    color: "#84cc16",
    info: "Population: 1.4 billion. Capital: New Delhi.",
  },
  AUS: {
    name: "Australia",
    color: "#14b8a6",
    info: "Population: 26 million. Capital: Canberra.",
  },
};

// Simplified world map paths (just a few countries as example)
// In production, you'd use a complete SVG map or a library like react-simple-maps
const countryPaths = {
  USA: "M150,120 L180,120 L180,140 L150,140 Z",
  CAN: "M140,80 L200,80 L200,115 L140,115 Z",
  MEX: "M150,145 L180,145 L180,165 L150,165 Z",
  BRA: "M220,180 L270,180 L270,240 L220,240 Z",
  GBR: "M280,100 L300,100 L300,115 L280,115 Z",
  FRA: "M300,120 L320,120 L320,140 L300,140 Z",
  DEU: "M320,105 L340,105 L340,125 L320,125 Z",
  CHN: "M480,120 L530,120 L530,160 L480,160 Z",
  IND: "M460,150 L500,150 L500,190 L460,190 Z",
  AUS: "M520,220 L580,220 L580,260 L520,260 Z",
};

export default function InteractiveMap() {
  const [selectedCountries, setSelectedCountries] = useState({});
  const [activeCountry, setActiveCountry] = useState(null);

  const handleCountryClick = (countryCode) => {
    // Toggle country selection
    if (selectedCountries[countryCode]) {
      const newSelected = { ...selectedCountries };
      delete newSelected[countryCode];
      setSelectedCountries(newSelected);
      setActiveCountry(null);
    } else {
      setSelectedCountries({
        ...selectedCountries,
        [countryCode]: countryData[countryCode],
      });
      setActiveCountry(countryCode);
    }
  };

  const clearAll = () => {
    setSelectedCountries({});
    setActiveCountry(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-6 text-white">
            <h1 className="text-3xl font-bold mb-2">Interactive World Map</h1>
            <p className="text-blue-100">
              Click on countries to select them and view information
            </p>
          </div>

          {/* Map Container */}
          <div className="p-8">
            <div className="bg-slate-50 rounded-xl p-6 mb-6">
              <svg viewBox="0 0 700 350" className="w-full h-auto">
                {/* Background */}
                <rect width="700" height="350" fill="#e0f2fe" />

                {/* Render countries */}
                {Object.entries(countryPaths).map(([code, path]) => {
                  const isSelected = selectedCountries[code];
                  const color = isSelected
                    ? countryData[code].color
                    : "#cbd5e1";

                  return (
                    <path
                      key={code}
                      d={path}
                      fill={color}
                      stroke="#64748b"
                      strokeWidth="1"
                      className="cursor-pointer transition-all duration-200 hover:opacity-80"
                      onClick={() => handleCountryClick(code)}
                    />
                  );
                })}
              </svg>
            </div>

            {/* Controls */}
            <div className="flex justify-between items-center mb-6">
              <div className="text-sm text-slate-600">
                <Info className="inline w-4 h-4 mr-1" />
                {Object.keys(selectedCountries).length}{" "}
                {Object.keys(selectedCountries).length === 1
                  ? "country"
                  : "countries"}{" "}
                selected
              </div>
              {Object.keys(selectedCountries).length > 0 && (
                <button
                  onClick={clearAll}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors flex items-center gap-2"
                >
                  <X className="w-4 h-4" />
                  Clear All
                </button>
              )}
            </div>

            {/* Country Information Panel */}
            {activeCountry && selectedCountries[activeCountry] && (
              <div className="bg-gradient-to-r from-slate-50 to-slate-100 rounded-xl p-6 border-l-4 border-blue-500 animate-in slide-in-from-bottom duration-300">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className="w-16 h-16 rounded-lg shadow-lg"
                      style={{
                        backgroundColor: countryData[activeCountry].color,
                      }}
                    />
                    <div>
                      <h3 className="text-2xl font-bold text-slate-800 mb-1">
                        {countryData[activeCountry].name}
                      </h3>
                      <p className="text-slate-600">
                        {countryData[activeCountry].info}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setActiveCountry(null)}
                    className="text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )}

            {/* Selected Countries List */}
            {Object.keys(selectedCountries).length > 0 && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold text-slate-800 mb-3">
                  Selected Countries
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {Object.entries(selectedCountries).map(([code, data]) => (
                    <div
                      key={code}
                      onClick={() => setActiveCountry(code)}
                      className="flex items-center gap-3 p-3 bg-white rounded-lg border border-slate-200 hover:border-slate-300 cursor-pointer transition-all hover:shadow-md"
                    >
                      <div
                        className="w-10 h-10 rounded-md shadow-sm flex-shrink-0"
                        style={{ backgroundColor: data.color }}
                      />
                      <span className="font-medium text-slate-700 text-sm">
                        {data.name}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-6 text-center text-slate-400 text-sm">
          <p>
            This is a demo with simplified country shapes. Replace with actual
            SVG map data for production use.
          </p>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { SearchIcon } from "@/components/icons";

export interface GeocodeResult {
  label: string;
  latitude: number;
  longitude: number;
}

// OpenStreetMap's public Nominatim geocoder — free, no API key, consistent
// with the app's existing token-free MapLibre + OSM raster tiles
// (components/map/osm-style.ts). Biased to a Mumbai bounding box since
// that's the app's whole coverage area. This is the public demo instance:
// fine for this app's light, debounced usage, but not meant for
// high-volume production traffic (see Nominatim's usage policy).
const MUMBAI_VIEWBOX = "72.75,19.30,73.05,18.85"; // left,top,right,bottom

async function searchNominatim(query: string): Promise<GeocodeResult[]> {
  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=5&countrycodes=in&viewbox=${MUMBAI_VIEWBOX}&bounded=1&q=${encodeURIComponent(query)}`;
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" } });
  } catch {
    return [];
  }
  if (!response.ok) return [];
  const data = (await response.json()) as { display_name: string; lat: string; lon: string }[];
  return data.map((d) => ({
    label: d.display_name,
    latitude: parseFloat(d.lat),
    longitude: parseFloat(d.lon),
  }));
}

export function LocationSearchInput({
  onSelect,
  placeholder,
}: {
  onSelect: (result: GeocodeResult) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const trimmed = query.trim();
    if (trimmed.length < 3) {
      setResults([]);
      return;
    }
    const requestId = ++requestIdRef.current;
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      const found = await searchNominatim(trimmed);
      if (requestId === requestIdRef.current) {
        setResults(found);
        setOpen(true);
        setLoading(false);
      }
    }, 450);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={containerRef}>
      <div className="relative">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-on-surface-variant" />
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder={placeholder ?? "Search a location… e.g. Andheri West"}
          className="w-full rounded-md border border-border-subtle bg-surface-container-lowest py-2 pl-9 pr-3 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      {open && (loading || results.length > 0) && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-border-subtle bg-surface-container-lowest shadow-card">
          {loading ? (
            <p className="px-3 py-2 text-xs text-on-surface-variant">Searching…</p>
          ) : (
            results.map((result, index) => (
              <button
                key={`${result.latitude}-${result.longitude}-${index}`}
                type="button"
                onClick={() => {
                  onSelect(result);
                  setQuery(result.label);
                  setOpen(false);
                }}
                className="block w-full truncate px-3 py-2 text-left text-xs text-on-surface hover:bg-surface-container-low"
                title={result.label}
              >
                {result.label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

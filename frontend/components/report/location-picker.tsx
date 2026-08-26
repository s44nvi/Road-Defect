"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { Map as MaplibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MUMBAI_CENTER, OSM_STYLE } from "@/components/map/osm-style";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { CrosshairIcon } from "@/components/icons";
import { LocationSearchInput } from "./location-search-input";

export interface Coordinates {
  latitude: number;
  longitude: number;
}

function isValidCoordinates(lat: number, lng: number): boolean {
  return !Number.isNaN(lat) && !Number.isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

// Reuses the same MapLibre + OSM setup as components/map/defect-map.tsx
// (components/map/osm-style.ts) rather than pulling in a second mapping
// library just for this one picker.
export function LocationPicker({
  value,
  onChange,
}: {
  value: Coordinates | null;
  onChange: (coords: Coordinates) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [latText, setLatText] = useState(value ? value.latitude.toFixed(5) : "");
  const [lngText, setLngText] = useState(value ? value.longitude.toFixed(5) : "");

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const start: [number, number] = value ? [value.longitude, value.latitude] : MUMBAI_CENTER;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: start,
      zoom: value ? 15 : 11,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

    const marker = new maplibregl.Marker({ color: "#006948", draggable: true }).setLngLat(start).addTo(map);

    marker.on("dragend", () => {
      const lngLat = marker.getLngLat();
      onChangeRef.current({ latitude: lngLat.lat, longitude: lngLat.lng });
    });
    map.on("click", (event) => {
      marker.setLngLat(event.lngLat);
      onChangeRef.current({ latitude: event.lngLat.lat, longitude: event.lngLat.lng });
    });

    mapRef.current = map;
    markerRef.current = marker;

    return () => {
      marker.remove();
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // Only ever initialize once — subsequent `value` changes are synced via
    // the effect below instead of re-creating the map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!value) return;
    setLatText(value.latitude.toFixed(5));
    setLngText(value.longitude.toFixed(5));

    const map = mapRef.current;
    const marker = markerRef.current;
    if (!map || !marker) return;
    marker.setLngLat([value.longitude, value.latitude]);
    map.easeTo({ center: [value.longitude, value.latitude], zoom: Math.max(map.getZoom(), 14) });
  }, [value?.latitude, value?.longitude]);

  function commit(nextLatText: string, nextLngText: string) {
    const lat = parseFloat(nextLatText);
    const lng = parseFloat(nextLngText);
    if (isValidCoordinates(lat, lng)) {
      onChangeRef.current({ latitude: lat, longitude: lng });
    }
  }

  function handleUseCurrentLocation() {
    if (!("geolocation" in navigator)) {
      setGeoError("Your browser doesn't support location detection. Enter coordinates manually below.");
      return;
    }
    setGeoLoading(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGeoLoading(false);
        onChangeRef.current({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        setGeoLoading(false);
        setGeoError(
          error.code === error.PERMISSION_DENIED
            ? "Location access was denied. Enter coordinates manually below."
            : "Couldn't detect your location. Enter coordinates manually below.",
        );
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <div className="space-y-3">
      <LocationSearchInput
        onSelect={(result) => onChangeRef.current({ latitude: result.latitude, longitude: result.longitude })}
      />

      <div className="h-56 overflow-hidden rounded-lg border border-border-subtle">
        <div ref={containerRef} className="h-full w-full" />
      </div>

      <Button
        type="button"
        variant="secondary"
        className="w-full"
        onClick={handleUseCurrentLocation}
        disabled={geoLoading}
      >
        <CrosshairIcon className="h-4 w-4" />
        {geoLoading ? "Detecting location…" : "Use my current location"}
      </Button>
      {geoError && <p className="text-xs text-error">{geoError}</p>}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="latitude">Latitude</Label>
          <Input
            id="latitude"
            inputMode="decimal"
            value={latText}
            onChange={(event) => {
              setLatText(event.target.value);
              commit(event.target.value, lngText);
            }}
            placeholder="19.07600"
          />
        </div>
        <div>
          <Label htmlFor="longitude">Longitude</Label>
          <Input
            id="longitude"
            inputMode="decimal"
            value={lngText}
            onChange={(event) => {
              setLngText(event.target.value);
              commit(latText, event.target.value);
            }}
            placeholder="72.87770"
          />
        </div>
      </div>
      <p className="text-xs text-on-surface-variant">
        Search for a place, click or drag the pin on the map, or enter coordinates directly.
      </p>
    </div>
  );
}

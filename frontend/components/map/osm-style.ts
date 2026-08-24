import type { StyleSpecification } from "maplibre-gl";

export const MUMBAI_CENTER: [number, number] = [72.8777, 19.076];

// Token-free OpenStreetMap raster tiles rendered through MapLibre GL JS
// (the open-source fork of Mapbox GL JS) — no API key needed. Note: for
// real production traffic this should move to a tile provider meant for
// that (e.g. MapTiler, or a self-hosted tile server) rather than hitting
// tile.openstreetmap.org directly, per OSM's tile usage policy — this is
// fine for local development and demos. Shared by DefectMap and the report
// flow's LocationPicker so both maps look and behave identically.
export const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

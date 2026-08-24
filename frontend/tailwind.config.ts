import type { Config } from "tailwindcss";

// Color/type/spacing tokens sourced from the Stitch RoadSense DESIGN.md
// (stitch_roadsense_civic_platform/roadsense/DESIGN.md), not invented here.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#fbf9f6",
        "on-background": "#1b1c1a",
        surface: "#fbf9f6",
        "surface-dim": "#dbdad7",
        "surface-bright": "#fbf9f6",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f5f3f0",
        "surface-container": "#efeeeb",
        "surface-container-high": "#eae8e5",
        "surface-container-highest": "#e4e2df",
        "surface-variant": "#e4e2df",
        "on-surface": "#1b1c1a",
        "on-surface-variant": "#3d4a42",
        "inverse-surface": "#30312f",
        "inverse-on-surface": "#f2f0ed",
        outline: "#6d7a72",
        "outline-variant": "#bccac0",
        "surface-tint": "#006c4a",
        primary: "#006948",
        "on-primary": "#ffffff",
        "primary-container": "#00855c",
        "on-primary-container": "#f5fff7",
        "inverse-primary": "#65dca8",
        secondary: "#555f6f",
        "on-secondary": "#ffffff",
        "secondary-container": "#d6e0f3",
        "on-secondary-container": "#596373",
        tertiary: "#9c3d3c",
        "on-tertiary": "#ffffff",
        "tertiary-container": "#bb5452",
        "on-tertiary-container": "#fffbff",
        error: "#ba1a1a",
        "on-error": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",
        // Literal card/input border used throughout the Stitch HTML
        // (border-[#E5E7EB]), kept distinct from the greener outline-variant
        // token since the two are visually different in the source screens.
        "border-subtle": "#e5e7eb",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
      },
      maxWidth: {
        "container-max": "1440px",
      },
      spacing: {
        "margin-mobile": "16px",
        "margin-desktop": "40px",
        gutter: "24px",
      },
      boxShadow: {
        card: "0px 4px 12px rgba(31, 41, 55, 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;

import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-plex-sans)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        severity: {
          critical: "#DC2626",
          high: "#EA580C",
          medium: "#CA8A04",
          low: "#6B7280",
        },
        confidence: {
          high: "#16A34A",
          medium: "#CA8A04",
          low: "#DC2626",
        },
        action: {
          auto: "#16A34A",
          approval: "#CA8A04",
          blocked: "#DC2626",
        },
      },
    },
  },
  plugins: [],
};

export default config;

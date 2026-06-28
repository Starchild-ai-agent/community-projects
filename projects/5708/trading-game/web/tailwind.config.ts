import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: { 900: "#0a0e17", 800: "#0f1420", 700: "#141a2a", 600: "#1a2236" },
        line: { DEFAULT: "#1a2236", soft: "#222a3d" },
        up: "#16c784",
        down: "#ea3943",
        warn: "#f0b90b",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        pulseRed: {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(234,57,67,0.55)" },
          "50%": { boxShadow: "0 0 0 8px rgba(234,57,67,0)" },
        },
        flash: { "0%": { opacity: "0.6" }, "100%": { opacity: "1" } },
      },
      animation: { pulseRed: "pulseRed 1.2s ease-in-out infinite", flash: "flash 0.6s ease-out" },
    },
  },
  plugins: [],
};
export default config;

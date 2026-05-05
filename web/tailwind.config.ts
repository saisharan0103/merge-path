import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#FAF8F3",
        ink: "#1A1A1A",
        edge: "#D4CFC0",
        forest: "#2D5016",
        oxblood: "#7C2D12",
        navy: "#1E3A8A",
      },
      fontFamily: {
        serif: ["'Source Serif Pro'", "Lora", "Georgia", "serif"],
        sans: ["Inter", "'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "Menlo", "monospace"],
      },
      borderRadius: { sm: "2px", DEFAULT: "3px", md: "4px" },
    },
  },
  plugins: [],
};

export default config;

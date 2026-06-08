import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#120f1d",
        night: "#191326",
        wine: "#44223b",
        gold: "#d9b56c",
        cream: "#f5ead7",
      },
      boxShadow: {
        glow: "0 0 40px rgba(217, 181, 108, 0.16)",
      },
    },
  },
  plugins: [],
};

export default config;

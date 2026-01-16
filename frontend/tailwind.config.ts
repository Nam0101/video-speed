import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "var(--background)",
                foreground: "var(--foreground)",
                primary: {
                    DEFAULT: "#0EA5E9",
                    light: "#38BDF8",
                    dark: "#0284C7",
                },
                accent: {
                    DEFAULT: "#F97316",
                    light: "#FDBA74",
                    dark: "#EA580C",
                },
                mint: "#22C55E",
                ink: "#0B1020",
                surface: "#FFFFFF",
                surfaceMuted: "#F8FAFC",
                border: {
                    DEFAULT: "rgba(148, 163, 184, 0.35)",
                    strong: "rgba(15, 23, 42, 0.12)",
                },
            },
            fontFamily: {
                sans: ["var(--font-body)"],
                heading: ["var(--font-display)"],
            },
            boxShadow: {
                sm: "0 8px 24px rgba(15, 23, 42, 0.08)",
                md: "0 16px 48px rgba(15, 23, 42, 0.12)",
                glow: "0 0 60px rgba(14, 165, 233, 0.25)",
            },
            animation: {
                "float-slow": "float 14s ease-in-out infinite",
                "float-medium": "float 10s ease-in-out infinite",
                shimmer: "shimmer 1.6s linear infinite",
                "fade-up": "fade-up 0.55s ease-out both",
                "fade-in": "fade-in 0.4s ease-out both",
                "pulse-soft": "pulse-soft 2.6s ease-in-out infinite",
            },
            keyframes: {
                float: {
                    "0%, 100%": {
                        transform: "translate(0px, 0px) scale(1)",
                    },
                    "50%": {
                        transform: "translate(20px, -30px) scale(1.05)",
                    },
                },
                shimmer: {
                    "0%": {
                        transform: "translateX(-100%)",
                    },
                    "100%": {
                        transform: "translateX(100%)",
                    },
                },
                "fade-up": {
                    "0%": {
                        opacity: "0",
                        transform: "translateY(18px)",
                    },
                    "100%": {
                        opacity: "1",
                        transform: "translateY(0)",
                    },
                },
                "fade-in": {
                    "0%": {
                        opacity: "0",
                    },
                    "100%": {
                        opacity: "1",
                    },
                },
                "pulse-soft": {
                    "0%, 100%": {
                        opacity: "0.6",
                        transform: "scale(1)",
                    },
                    "50%": {
                        opacity: "1",
                        transform: "scale(1.05)",
                    },
                },
            },
        },
    },
    plugins: [],
};

export default config;

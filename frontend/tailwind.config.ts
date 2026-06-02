import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          muted: "hsl(var(--primary-muted))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // 漲跌（台股慣例：紅漲綠跌）
        bull: {
          DEFAULT: "hsl(var(--bull))",
          foreground: "hsl(var(--bull-foreground))",
          muted: "hsl(var(--bull-muted))",
        },
        bear: {
          DEFAULT: "hsl(var(--bear))",
          foreground: "hsl(var(--bear-foreground))",
          muted: "hsl(var(--bear-muted))",
        },
        flat: {
          DEFAULT: "hsl(var(--flat))",
          muted: "hsl(var(--flat-muted))",
        },
        // 訊號
        "signal-buy": {
          DEFAULT: "hsl(var(--signal-buy))",
          foreground: "hsl(var(--signal-buy-foreground))",
          muted: "hsl(var(--signal-buy-muted))",
        },
        "signal-sell": {
          DEFAULT: "hsl(var(--signal-sell))",
          foreground: "hsl(var(--signal-sell-foreground))",
          muted: "hsl(var(--signal-sell-muted))",
        },
        "signal-hold": {
          DEFAULT: "hsl(var(--signal-hold))",
          foreground: "hsl(var(--signal-hold-foreground))",
          muted: "hsl(var(--signal-hold-muted))",
        },
        // Stage
        "state-pending": {
          DEFAULT: "hsl(var(--state-pending))",
          muted: "hsl(var(--state-pending-muted))",
        },
        "state-running": {
          DEFAULT: "hsl(var(--state-running))",
          muted: "hsl(var(--state-running-muted))",
        },
        "state-done": {
          DEFAULT: "hsl(var(--state-done))",
          muted: "hsl(var(--state-done-muted))",
        },
        "state-failed": {
          DEFAULT: "hsl(var(--state-failed))",
          muted: "hsl(var(--state-failed-muted))",
        },
        // Status
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        chart: {
          "1": "hsl(var(--chart-1))",
          "2": "hsl(var(--chart-2))",
          "3": "hsl(var(--chart-3))",
          "4": "hsl(var(--chart-4))",
          "5": "hsl(var(--chart-5))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "calc(var(--radius) + 4px)",
        "2xl": "calc(var(--radius) + 8px)",
      },
      ringWidth: {
        DEFAULT: "3px",
        "3": "3px",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        soft: "0 1px 2px hsl(0 0% 0% / 0.04), 0 1px 1px hsl(0 0% 0% / 0.02)",
        lift: "0 4px 12px hsl(var(--primary) / 0.08)",
        glow: "0 0 0 4px hsl(var(--primary) / 0.12)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 hsl(var(--state-running) / 0.4)" },
          "50%": { boxShadow: "0 0 0 6px hsl(var(--state-running) / 0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
        shimmer: "shimmer 2s linear infinite",
        "pulse-glow": "pulse-glow 1.6s ease-in-out infinite",
      },
    },
  },
  // 確保動態 class 不被 purge
  safelist: [
    "bg-bull",
    "bg-bear",
    "bg-bull-muted",
    "bg-bear-muted",
    "text-bull",
    "text-bear",
    "bg-signal-buy",
    "bg-signal-sell",
    "bg-signal-hold",
    "bg-signal-buy-muted",
    "bg-signal-sell-muted",
    "bg-signal-hold-muted",
    "text-signal-buy",
    "text-signal-sell",
    "text-signal-hold",
    "bg-state-pending",
    "bg-state-running",
    "bg-state-done",
    "bg-state-failed",
    "bg-state-pending-muted",
    "bg-state-running-muted",
    "bg-state-done-muted",
    "bg-state-failed-muted",
    "text-state-pending",
    "text-state-running",
    "text-state-done",
    "text-state-failed",
    "border-state-pending",
    "border-state-running",
    "border-state-done",
    "border-state-failed",
    "border-bull",
    "border-bear",
  ],
  plugins: [animate],
};

export default config;

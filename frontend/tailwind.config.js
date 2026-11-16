/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        serif: ['"Crimson Pro"', '"Georgia"', 'serif'],
      },
      colors: {
        // Custom theorem-prover palette
        ink: {
          50: '#f0f1f5',
          100: '#d9dce6',
          200: '#b3b9cd',
          300: '#8d96b4',
          400: '#67739b',
          500: '#4a5578',
          600: '#3b4461',
          700: '#2c334a',
          800: '#1e2233',
          900: '#131623',
          950: '#0b0d17',
        },
        accent: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        proof: {
          green: '#34d399',
          red: '#f87171',
          amber: '#fbbf24',
          blue: '#60a5fa',
          violet: '#a78bfa',
        },
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.03)',
        'card-hover': '0 4px 12px 0 rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.04)',
        'sidebar': '2px 0 8px 0 rgba(0, 0, 0, 0.15)',
      },
    },
  },
  plugins: [],
};

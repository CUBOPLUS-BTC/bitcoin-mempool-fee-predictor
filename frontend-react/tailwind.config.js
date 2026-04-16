/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        'mempool-blue': '#3d5afe',
        'mempool-yellow': '#f5d41f',
        'mempool-orange': '#f7931a',
        'neon-green': '#00ff41',
        'terminal-bg': '#050505',
        'terminal-text': '#e0e0e0',
      },
      animation: {
        'blink': 'blink 1s step-start infinite',
      },
      keyframes: {
        blink: {
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}

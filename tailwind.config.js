/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-dark':  '#0a0a0f',
        'blue-e':   '#00d4ff',
        'purple-e': '#7b2fff',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'float':       'float 6s ease-in-out infinite',
        'float-slow':  'float 9s ease-in-out infinite',
        'glow-pulse':  'glowPulse 3s ease-in-out infinite alternate',
        'spin-slow':   'spin 25s linear infinite',
        'border-glow': 'borderGlow 3s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%,100%': { transform: 'translateY(0px)' },
          '50%':     { transform: 'translateY(-18px)' },
        },
        glowPulse: {
          from: { boxShadow: '0 0 15px rgba(0,212,255,0.3), 0 0 30px rgba(0,212,255,0.1)' },
          to:   { boxShadow: '0 0 25px rgba(123,47,255,0.4), 0 0 50px rgba(123,47,255,0.15)' },
        },
        borderGlow: {
          '0%,100%': { borderColor: 'rgba(0,212,255,0.4)' },
          '50%':     { borderColor: 'rgba(123,47,255,0.7)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-glow':       'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,212,255,0.15), transparent)',
      },
    },
  },
  plugins: [],
}

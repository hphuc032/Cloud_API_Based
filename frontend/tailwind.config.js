/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#1B2A4A',
          50: '#EEF1F6',
          100: '#D7DEEA',
          200: '#AFBED5',
          400: '#5A6E94',
          600: '#2C3F66',
          700: '#1B2A4A',
          800: '#141F38',
          900: '#0D1526',
        },
        sage: {
          DEFAULT: '#3FA796',
          50: '#EBF7F4',
          100: '#D2EDE7',
          400: '#5FBBAC',
          500: '#3FA796',
          600: '#2E8A7B',
          700: '#236B60',
        },
        bloom: {
          DEFAULT: '#F4B6C2',
          50: '#FDF1F3',
          100: '#FBE2E7',
          300: '#F7C9D2',
          500: '#F4B6C2',
          600: '#E891A2',
        },
        canvas: '#FAFAF8',
        ink: {
          DEFAULT: '#1F2430',
          muted: '#6B7280',
          faint: '#9CA3AF',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgba(27, 42, 74, 0.04), 0 2px 8px -2px rgba(27, 42, 74, 0.08)',
        cardHover: '0 4px 12px -2px rgba(27, 42, 74, 0.12)',
      },
      borderRadius: {
        xl2: '1rem',
      },
    },
  },
  plugins: [],
}

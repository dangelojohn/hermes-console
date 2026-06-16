/** @type {import('tailwindcss').Config} */
import forms from '@tailwindcss/forms';

export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        priority: {
          blocker: '#dc2626', // red-600
          high: '#ea580c',    // orange-600
          normal: '#2563eb',  // blue-600
          low: '#6b7280',     // gray-500
        },
        health: {
          ok: '#16a34a',
          warn: '#d97706',
          err: '#dc2626',
        },
        brand: {
          DEFAULT: '#7c3aed', // hermes purple
          dark: '#5b21b6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [forms],
};

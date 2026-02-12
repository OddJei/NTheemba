import type { Config } from "tailwindcss";

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ntheemba: {
          // Primary emerald green from background
          primary: '#059669',
          secondary: '#10B981',
          // Orange gradient colors from logo shapes
          orange: {
            50: '#FFF7ED',
            100: '#FFEDD5',
            200: '#FED7AA',
            300: '#FDBA74',
            400: '#FB923C',
            500: '#E98F2C', // Main orange from text
            600: '#E9902D', // Light orange from gradient
            700: '#C14A0C', // Medium orange from gradient
            800: '#C04208', // Dark orange from gradient
            900: '#7C2D12',
          },
          // Supporting colors
          green: {
            50: '#F0FDF4',
            100: '#DCFCE7',
            200: '#BBF7D0',
            300: '#86EFAC',
            400: '#4ADE80',
            500: '#059669', // Primary green
            600: '#10B981',
            700: '#047857',
            800: '#065F46',
            900: '#064E3B',
          }
        }
      },
      fontFamily: {
        'poppins': ['Poppins', 'Arial', 'sans-serif'],
        'hanken': ['Hanken Grotesk', 'Poppins', 'Arial', 'sans-serif']
      }
    },
  },
  plugins: [],
} satisfies Config;
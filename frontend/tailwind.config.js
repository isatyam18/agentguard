/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#070C1E',
          900: '#0B132B',
          850: '#131D38',
          800: '#1C2541',
          700: '#2E3D66',
          600: '#3A506B',
          500: '#4D688D',
        },
      },
    },
  },
  plugins: [],
};

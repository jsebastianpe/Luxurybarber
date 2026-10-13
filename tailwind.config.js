/** Tokens del sistema de diseño "Navaja y Cuero". Compila con: npm run build:css */
module.exports = {
  content: ["./templates/**/*.html", "./core/**/*.py"],
  theme: {
    extend: {
      colors: {
        carbon: { 950: "#14110F", 900: "#1A1714", 800: "#23201D", 700: "#2D2925", 600: "#3A3531" },
        marfil: { 50: "#F7F2EA", 100: "#EFE7DA" },
        piedra: { 400: "#9A928A", 500: "#7A736C" },
        laton: { 400: "#D7B776", 500: "#C9A45C", 700: "#8E6F33" },
        cuero: { 600: "#8A4B2C" },
        poste: "#A3312A",
        salvia: "#4F8A63",
        ambar: "#D19A2A",
      },
      fontFamily: {
        display: ['"DM Serif Display"', "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: { card: "10px" },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Electron development: standard Vite dev server
export default defineConfig({
  plugins: [react()],
  server: {
    host: "localhost",
    port: 5174,
    strictPort: true
  },
  clearScreen: false
});

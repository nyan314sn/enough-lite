import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5197. /api goes to the lite backend (port 8020) unless VITE_MOCK=1, where src/mock.ts answers instead.
// The built app calls relative /api paths, so it works on whatever host serves it.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5197,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8020", changeOrigin: true } },
  },
  build: { outDir: "dist", emptyOutDir: true },
});

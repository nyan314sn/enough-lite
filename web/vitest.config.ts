import { defineConfig } from "vitest/config";

// Tests run in jsdom. esbuild handles the JSX (vitest ships its own vite, so the React plugin is not needed here).
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});

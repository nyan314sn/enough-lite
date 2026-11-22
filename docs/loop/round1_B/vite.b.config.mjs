import { fileURLToPath } from "node:url";
export default {
  root: fileURLToPath(new URL("../../../web", import.meta.url)),
  esbuild: { jsx: "automatic" },
  base: "./",
  server: { port: 5182, strictPort: true, proxy: { "/api": { target: "http://localhost:8032", changeOrigin: true } } },
};

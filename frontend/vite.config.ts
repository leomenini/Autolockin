import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // `npm run dev` talks to the real daemon on 8420.
    proxy: {
      "/api": "http://127.0.0.1:8420",
      "/ws": { target: "ws://127.0.0.1:8420", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});

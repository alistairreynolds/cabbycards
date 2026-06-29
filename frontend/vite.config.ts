/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url"

import tailwindcss from "@tailwindcss/vite"
import vue from "@vitejs/plugin-vue"
import { defineConfig } from "vite"

// Local dev → localhost:8000; in Docker the compose file sets BACKEND_URL=http://backend:8000.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000"

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: true,
    proxy: {
      // Send API calls to the FastAPI backend, stripping the /api prefix
      // (backend routes are /auth/*, /cards/* with no prefix). Avoids CORS setup.
      "/api": {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
})

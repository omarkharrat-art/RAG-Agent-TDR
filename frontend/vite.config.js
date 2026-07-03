import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base URL is read at runtime from VITE_API_BASE (see src/services/api.js).
// In dev we also proxy /api -> backend so the frontend can call it without CORS
// concerns if you prefer a same-origin setup.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});

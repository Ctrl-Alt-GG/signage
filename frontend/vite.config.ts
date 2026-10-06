import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Built assets are served by Django (WhiteNoise) under /static/display/ and
// referenced from the display template through django-vite's manifest reader.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/display/",
  build: {
    outDir: "dist",
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {
      input: "src/main.tsx",
    },
  },
  server: {
    host: "localhost",
    port: 5173,
    origin: "http://localhost:5173",
    cors: true,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});

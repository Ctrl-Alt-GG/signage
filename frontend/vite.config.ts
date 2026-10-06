import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The build is a static site served by nginx (docker/frontend.Dockerfile), which also
// proxies the backend paths. In development Vite plays that role: it serves the app and
// forwards the same paths to the Django development server.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
const proxy = {
  "/api": backend,
  "/admin": backend,
  "/health": backend,
  "/static": backend,
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    host: "localhost",
    port: 5173,
    proxy,
  },
  preview: {
    host: "localhost",
    port: 4173,
    proxy,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});

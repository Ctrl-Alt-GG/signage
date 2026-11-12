import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The build is a static site served by nginx (docker/frontend.Dockerfile), which also
// proxies the backend paths. In development Vite plays that role: it serves the app and
// forwards the same paths to the Django development server.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
// Like nginx, the proxy keeps the Host the browser asked for. Django compares it with the
// Origin of a form post, so with the backend's own host there the admin login is refused.
const toBackend = { target: backend, changeOrigin: false, xfwd: true };
const proxy = {
  "/api": toBackend,
  "/admin": toBackend,
  "/health": toBackend,
  "/static": toBackend,
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

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5172,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8102", changeOrigin: false } },
  },
  build: {
    rollupOptions: { output: { manualChunks: { recharts: ["recharts"], react: ["react", "react-dom", "react-router-dom"] } } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});

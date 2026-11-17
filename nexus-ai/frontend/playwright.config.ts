import { defineConfig } from "@playwright/test";

// E2E runs against a live stack: API on :8101 (seeded) and Vite on :5171.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: false,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5171", viewport: { width: 1440, height: 900 } },
  reporter: [["list"]],
});

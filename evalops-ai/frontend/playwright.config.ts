import { defineConfig } from "@playwright/test";

// E2E against a live stack (docker compose up): web on :5173 proxies /api to :8103.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173", viewport: { width: 1440, height: 900 } },
  reporter: [["list"]],
});

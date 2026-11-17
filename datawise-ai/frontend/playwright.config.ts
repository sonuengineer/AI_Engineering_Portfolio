import { defineConfig } from "@playwright/test";

// E2E against a live stack (docker compose up): web on :5172 proxies /api to :8102.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5172", viewport: { width: 1440, height: 900 } },
  reporter: [["list"]],
});

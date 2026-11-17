import { expect, test, type Page } from "@playwright/test";

// Uses a dedicated viewer account created with scripts/create_user.py (see docs/testing.md).
const EMAIL = process.env.E2E_EMAIL ?? "e2e-viewer@evalops.local";
const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-viewer-local-only";
const SHOTS = "../docs/screenshots";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("link", { name: /NEXUS AI RAG benchmark/ })).toBeVisible();
}

test("live NEXUS benchmark run shows deterministic metrics", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: /NEXUS AI RAG benchmark/ }).click();
  await page.getByRole("link", { name: "NEXUS live (local adapter), dataset v2" }).click();
  await expect(page.getByRole("region", { name: "Quality metrics" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Per-case results" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/evalops-run.png`, fullPage: true });
});

test("comparing two runs highlights regressions", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: /Support Assistant QA/ }).click();
  const boxes = page.getByRole("checkbox", { name: /Select run .* for comparison/ });
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("button", { name: /Compare selected/ }).click();
  await expect(page.getByRole("region", { name: "Metric deltas" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Case changes" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/evalops-compare.png`, fullPage: true });
});

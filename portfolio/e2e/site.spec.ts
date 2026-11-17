import { expect, test } from "@playwright/test";

const SHOTS = "docs/screenshots";

test("home lists three projects and labels placeholders honestly", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 3, name: "NEXUS AI" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "DATAWISE AI" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "EVALOPS AI" })).toBeVisible();
  await expect(page.getByText("GitHub: not configured")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/portfolio-home.png`, fullPage: true });
});

test("project page shows architecture, real screenshots and measured artifacts", async ({ page }) => {
  await page.goto("/projects/nexus-ai");
  await expect(page.getByRole("heading", { level: 1, name: "NEXUS AI" })).toBeVisible();
  await expect(page.getByRole("figure", { name: /architecture layers/ })).toBeVisible();
  await expect(page.getByText("nexus-ai/docs/benchmarks/latency.json")).toBeVisible();
  await expect(page.getByText("Live demo: not configured")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/portfolio-project.png`, fullPage: true });
});

test("interview flow: project -> topic -> difficulty -> reveal -> learned", async ({ page }) => {
  await page.goto("/interview");
  await page.getByRole("link", { name: /Cross-project/ }).click();
  await page.getByLabel("1. Topic").selectOption("safety-patterns");
  await page.getByRole("button", { name: "advanced", exact: true }).click();
  await page.getByRole("button", { name: "Reveal answer" }).click();
  await expect(page.getByText("Expected answer")).toBeVisible();
  await expect(page.getByText("Likely follow-ups")).toBeVisible();
  await page.getByRole("button", { name: "Mark learned" }).click();
  await expect(page.getByRole("button", { name: "Learned" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/portfolio-interview.png`, fullPage: true });
  await page.goto("/interview");
  await expect(page.getByText(/1 learned/)).toBeVisible();
});

test("evalops page shows live benchmark artifact exported from stored runs", async ({ page }) => {
  await page.goto("/projects/evalops-ai");
  await expect(page.getByText("evalops-ai/docs/benchmarks/live-benchmarks.json")).toBeVisible();
  await expect(page.getByText(/NEXUS live \(local adapter\), dataset v2/).first()).toBeVisible();
  await page.screenshot({ path: "docs/screenshots/portfolio-evalops.png", fullPage: true });
});

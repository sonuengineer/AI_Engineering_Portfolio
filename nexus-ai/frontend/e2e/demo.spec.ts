import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "change-me-demo-password";
const SHOTS = "../docs/screenshots";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Ask your enterprise knowledge" })).toBeVisible();
}

test("grounded Q&A with citations and abstention", async ({ page }) => {
  await login(page, "analyst@acme.example");
  await page.getByRole("region", { name: "Chat" }).getByRole("button", { name: "Why did Harbor Marine Systems reject batch MC-5521?" }).click();
  await expect(page.getByText(/Grounded: \d+ source/)).toBeVisible();
  await expect(page.getByText(/Harbor Marine Systems -- Non-Conformance Report NCR-2026-117, page 1/).first()).toBeVisible();
  await page.getByLabel("Question").fill("What is the capital of France?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Insufficient evidence")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/nexus-chat.png`, fullPage: true });
});

test("investigation -> evidence/hypotheses -> human approval", async ({ page }) => {
  await login(page, "manager@acme.example");
  await page.getByRole("link", { name: "Investigations" }).click();
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(page.getByText("Findings: evidence vs hypotheses")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("awaiting approval").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Northwind Fabrication", exact: true }).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/nexus-investigation.png`, fullPage: true });

  const card = page.getByRole("article", { name: /Approval for Northwind Fabrication/ });
  await card.getByRole("button", { name: "Approve and send" }).click();
  await expect(card.getByText(/Delivered to the local outbox connector/)).toBeVisible();

  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByText("Model usage and estimated cost")).toBeVisible();
  await expect(page.getByText(/account review/i).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/nexus-admin.png`, fullPage: true });
});

test("documents page shows ingestion status and injection flag", async ({ page }) => {
  await login(page, "analyst@acme.example");
  await page.getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("cell", { name: /Suspicious Vendor Note injection flagged/ })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/nexus-documents.png`, fullPage: true });
});

test("viewer cannot start investigations or approve", async ({ page }) => {
  await login(page, "viewer@acme.example");
  await page.getByRole("link", { name: "Investigations" }).click();
  await expect(page.getByRole("button", { name: "Run investigation" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
});

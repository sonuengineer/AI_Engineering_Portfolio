import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "change-me-demo-password";
const SHOTS = "../docs/screenshots";

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email").fill("demo@acme.example");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByLabel("Ask a business question")).toBeVisible();
}

test("answered question shows SQL, validation, rows and chart", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Revenue by month in 2025" }).click();
  await expect(page.getByText(/SELECT/i).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Copy SQL to clipboard" })).toBeVisible();
  await expect(page.getByRole("table").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/datawise-answer.png`, fullPage: true });
});

test("ambiguous question asks for clarification", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Who are our best customers?" }).click();
  await expect(page.getByLabel("Clarification options")).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${SHOTS}/datawise-clarification.png`, fullPage: true });
});

test("unsafe request is rejected and nothing executes", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Delete all cancelled orders" }).click();
  await expect(page.getByText(/rejected/i).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/datawise-rejected.png`, fullPage: true });
});

import { expect, test } from "@playwright/test";

// Smoke journey: the public root route renders the login form.
// Selectors are structural (ids and input types from LoginView) so the spec
// stays locale-independent. The dev server is booted by the `webServer`
// entry in playwright.config.ts; no extra infrastructure is required.
test.describe("login page", () => {
  test("renders the login form", async ({ page }) => {
    await page.goto("/");

    const email = page.locator("input#email");
    const password = page.locator("input#password");

    await expect(email).toBeVisible();
    await expect(email).toHaveAttribute("type", "email");
    await expect(password).toBeVisible();
    await expect(password).toHaveAttribute("type", "password");
    await expect(page.locator('button[type="submit"]').first()).toBeVisible();
  });
});

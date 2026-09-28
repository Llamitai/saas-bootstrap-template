import { expect, test } from "@playwright/test";
import {
  seedUserWithTenants,
  signIn,
} from "@/tests/end-to-end/support/tenant-user";

// The shell is mounted once by the (shell) layout: navigating between shell
// pages keeps the same sidebar DOM node while breadcrumb and title follow the
// route. Selected only by the isolated real-API integration runner.
test("shell persists across navigation while breadcrumb and title follow the route", async ({
  page,
  request,
}) => {
  const { email, password } = await seedUserWithTenants(request);
  await signIn(page, email, password);
  await expect(page).toHaveURL(/\/members$/);
  await expect(page).toHaveTitle(/^Miembros \|/);

  const sidebar = page.locator('[data-sidebar="sidebar"]').first();
  await sidebar.evaluate((node) => {
    node.setAttribute("data-e2e-probe", "mounted-once");
  });
  const breadcrumb = page
    .getByRole("navigation", { name: "Ruta de navegación" })
    .first();

  await page.getByRole("link", { name: "Roles", exact: true }).click();
  await expect(page).toHaveURL(/\/roles$/);
  await expect(breadcrumb.getByText("Roles", { exact: true })).toBeVisible();
  await expect(page).toHaveTitle(/^Roles \|/);

  await page.getByRole("link", { name: "Configuración", exact: true }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(
    breadcrumb.getByText("Configuración", { exact: true })
  ).toBeVisible();

  await expect(sidebar).toHaveAttribute("data-e2e-probe", "mounted-once");
});

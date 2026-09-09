import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { COOKIE_ACCESS_TOKEN, COOKIE_REFRESH_TOKEN } from "@/src/constants";

// This suite is selected only by the isolated real-API integration runner.
// No request interception: credentials are submitted by the browser to the BFF.
test("invalid login recovers, creates HttpOnly session and logs out", async ({
  page,
  request,
  context,
}) => {
  const apiURL = process.env.E2E_API_URL;
  const apiKey = process.env.E2E_API_KEY;
  if (!apiURL || !apiKey)
    throw new Error("Use just integration with its exclusive API stack");
  const email = `session-${randomUUID()}@example.com`;
  const password = "Test-password-1234";
  const created = await request.post(`${apiURL}/v1/users`, {
    headers: { "x-api-key": apiKey },
    data: { email, password },
  });
  expect(created.status()).toBe(201);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill("incorrect-password");
  const rejected = page.waitForResponse((r) =>
    r.url().endsWith("/api/auth/login")
  );
  await page.locator('button[type="submit"]').click();
  expect((await rejected).ok()).toBe(false);
  await expect(page.locator("form").getByRole("alert")).toBeVisible();

  await page.locator("#password").fill(password);
  await page.locator("#password").press("Tab");
  const accepted = page.waitForResponse((r) =>
    r.url().endsWith("/api/auth/login")
  );
  await page.locator('button[type="submit"]').click();
  const response = await accepted;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.data.user).toMatchObject({ emailAddress: { email } });
  expect(body.data).not.toHaveProperty("session");
  await expect(page).toHaveURL(/\/unassigned$/);
  const cookies = (await context.cookies()).filter((cookie) =>
    [COOKIE_ACCESS_TOKEN, COOKIE_REFRESH_TOKEN].includes(cookie.name)
  );
  expect(cookies).toHaveLength(2);
  expect(
    cookies.every((cookie) => cookie.httpOnly && cookie.sameSite === "Lax")
  ).toBe(true);
  const visibleCookies = await page.evaluate(() => document.cookie);
  expect(visibleCookies).not.toContain(COOKIE_REFRESH_TOKEN);
  expect(visibleCookies).not.toContain(COOKIE_ACCESS_TOKEN);

  const logout = page.getByRole("button", { name: "Salir", exact: true });
  await logout.focus();
  await expect(logout).toBeFocused();
  await logout.press("Enter");
  await expect(page.locator("#email")).toBeVisible();
  expect(
    (await context.cookies()).filter((cookie) =>
      [COOKIE_ACCESS_TOKEN, COOKIE_REFRESH_TOKEN].includes(cookie.name)
    )
  ).toHaveLength(0);
});

import { type BrowserContext, expect, type Page, test } from "@playwright/test";
import { COOKIE_ACCESS_TOKEN, COOKIE_REFRESH_TOKEN } from "@/src/constants";
import {
  apiEnv,
  seedUserWithTenants,
  signIn,
  type Tenant,
} from "@/tests/end-to-end/support/tenant-user";

// AC-01: the session survives hard reloads, a missing access cookie and a
// tenant switch, and the refresh cookie left in the browser stays valid.
// Selected only by the isolated real-API integration runner (just integration).

async function expectMembersPage(page: Page, tenant: Tenant) {
  await expect(page).toHaveURL(/\/members$/);
  await expect(page.getByText(tenant.name).first()).toBeVisible();
}

async function sessionCookie(context: BrowserContext, name: string) {
  return (await context.cookies()).find((cookie) => cookie.name === name);
}

test("session survives reloads, a missing access cookie and a tenant switch", async ({
  page,
  request,
  context,
}) => {
  const { apiURL, apiKey } = apiEnv();
  const { email, password, tenants } = await seedUserWithTenants(request);
  const [first, second] = tenants;

  await signIn(page, email, password);
  await expectMembersPage(page, first);

  await page.reload();
  await expectMembersPage(page, first);
  await page.reload();
  await expectMembersPage(page, first);

  // Expired/missing access cookie with a valid refresh cookie: the proxy
  // rotates, writes both cookies and renders without bouncing to login.
  const refreshBefore = await sessionCookie(context, COOKIE_REFRESH_TOKEN);
  await context.clearCookies({ name: COOKIE_ACCESS_TOKEN });
  await page.reload();
  await expectMembersPage(page, first);
  expect(await sessionCookie(context, COOKIE_ACCESS_TOKEN)).toBeDefined();
  const refreshAfter = await sessionCookie(context, COOKIE_REFRESH_TOKEN);
  expect(refreshAfter?.value).toBeTruthy();
  expect(refreshAfter?.value).not.toBe(refreshBefore?.value);
  expect(refreshAfter?.httpOnly).toBe(true);

  // Tenant switch does a hard reload of the current protected page.
  await page.getByRole("button", { name: new RegExp(first.name) }).click();
  const switched = page.waitForEvent("load");
  await page.getByRole("menuitem", { name: new RegExp(second.name) }).click();
  await switched;
  await expectMembersPage(page, second);
  await page.reload();
  await expectMembersPage(page, second);

  // The refresh cookie the browser kept is still accepted by the backend.
  const finalRefresh = await sessionCookie(context, COOKIE_REFRESH_TOKEN);
  expect(finalRefresh?.value).toBeTruthy();
  const accepted = await request.post(`${apiURL}/v1/auth/refresh`, {
    headers: { "x-api-key": apiKey },
    data: { refreshToken: finalRefresh?.value },
  });
  expect(accepted.status()).toBe(200);
});

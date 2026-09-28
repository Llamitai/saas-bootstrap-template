import { randomUUID } from "node:crypto";
import { type APIRequestContext, expect, type Page } from "@playwright/test";

// Seeds a user who owns two tenants through the real API of the exclusive
// integration stack (just integration) and signs them in through the BFF.

export type Tenant = { uuid: string; name: string };

export function apiEnv() {
  const apiURL = process.env.E2E_API_URL;
  const apiKey = process.env.E2E_API_KEY;
  if (!apiURL || !apiKey)
    throw new Error("Use just integration with its exclusive API stack");
  return { apiURL, apiKey };
}

export async function seedUserWithTenants(request: APIRequestContext) {
  const { apiURL, apiKey } = apiEnv();
  const email = `tenant-session-${randomUUID()}@example.com`;
  const password = "Test-password-1234";
  const headers = { "x-api-key": apiKey };

  const created = await request.post(`${apiURL}/v1/users`, {
    headers,
    data: { email, password },
  });
  expect(created.status()).toBe(201);

  const login = await request.post(`${apiURL}/v1/auth/login`, {
    headers,
    data: { email, password },
  });
  expect(login.ok()).toBe(true);
  const accessToken: string = (await login.json()).data.session.accessToken;
  const authHeaders = { ...headers, authorization: `Bearer ${accessToken}` };

  const tenants: Tenant[] = [];
  for (const name of ["Acme Norte", "Acme Sur"]) {
    const registered = await request.post(`${apiURL}/v1/tenants`, {
      headers: authHeaders,
      data: { name: `${name} ${randomUUID().slice(0, 6)}` },
    });
    expect(registered.ok()).toBe(true);
    const body = await registered.json();
    const tenant = body.data ?? body;
    tenants.push({ uuid: tenant.uuid, name: tenant.name });
  }

  const selected = await request.put(
    `${apiURL}/v1/me/tenants/${tenants[0].uuid}`,
    { headers: authHeaders }
  );
  expect(selected.ok()).toBe(true);
  return { email, password, tenants };
}

export async function signIn(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.locator('button[type="submit"]').click();
}

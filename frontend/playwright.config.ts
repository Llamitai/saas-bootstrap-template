import { defineConfig } from "@playwright/test";

const port = Number(process.env.E2E_PORT || "3100");
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("E2E_PORT must be a valid TCP port");
}
const baseURL = `http://127.0.0.1:${port}`;
const runId = process.env.E2E_RUN_ID || "local";
if (!/^[a-zA-Z0-9_-]+$/.test(runId)) throw new Error("Invalid E2E_RUN_ID");

export default defineConfig({
  testDir: "./tests/end-to-end",
  testIgnore:
    process.env.E2E_INTEGRATION === "1" ? [] : ["**/*.integration.spec.ts"],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  outputDir: `tests/reports/playwright/${runId}/artifacts`,
  reporter: [
    [
      "html",
      {
        outputFolder: `tests/reports/playwright/${runId}/html`,
        open: "never",
      },
    ],
  ],
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
  webServer: {
    command: `pnpm dev --hostname 127.0.0.1 --port ${port}`,
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120000,
  },
});

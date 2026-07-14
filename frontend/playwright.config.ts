import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/end-to-end",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  outputDir: "tests/reports/playwright/artifacts",
  reporter: [
    [
      "html",
      {
        outputFolder: "tests/reports/playwright/html",
        open: "never",
      },
    ],
  ],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 30000,
  },
});

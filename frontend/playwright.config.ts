import { defineConfig, devices } from "@playwright/test";

const liveUrl = process.env.E2E_LIVE_URL?.replace(/\/$/, "");
const localUrl = "http://127.0.0.1:3100";
const mockApiUrl = "https://api.example.invalid";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [["line"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL: liveUrl ?? localUrl,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: liveUrl
    ? undefined
    : {
        command:
          "npm run build && npm run start -- --hostname 127.0.0.1 --port 3100",
        url: `${localUrl}/widget`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          NEXT_PUBLIC_CHAT_API_URL: mockApiUrl,
          PRIVACY_NOTICE_VERSION: "ci-approved-v1",
          PRIVACY_NOTICE_ES: "Aviso de privacidad para pruebas automatizadas.",
          PRIVACY_NOTICE_EN: "Privacy notice for automated tests.",
          WIDGET_FRAME_ANCESTORS: "'self' https://example.invalid",
        },
      },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

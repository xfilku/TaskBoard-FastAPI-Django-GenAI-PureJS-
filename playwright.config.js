const { defineConfig } = require("@playwright/test");
const { mkdtempSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const { randomBytes } = require("node:crypto");

const python = process.env.TASKBOARD_TEST_PYTHON || "python";
const temporaryDirectory = mkdtempSync(path.join(tmpdir(), "taskboard-e2e-"));
const environment = {
  TASKBOARD_E2E_DIR: temporaryDirectory,
  TASKBOARD_JWT_SECRET: randomBytes(48).toString("base64url"),
  DJANGO_SECRET_KEY: randomBytes(48).toString("base64url"),
  DJANGO_DEBUG: "true",
  DJANGO_ALLOWED_HOSTS: "127.0.0.1,localhost",
  TASKBOARD_AI_PROVIDER: "demo",
  TASKBOARD_API_URL: "http://127.0.0.1:18180/",
};

module.exports = defineConfig({
  testDir: "./frontend/e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:18100",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -B scripts/e2e_server.py api`,
      url: "http://127.0.0.1:18180/health",
      env: environment,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `"${python}" -B scripts/e2e_server.py frontend`,
      url: "http://127.0.0.1:18100/login/",
      env: environment,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

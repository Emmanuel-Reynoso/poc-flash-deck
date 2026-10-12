import { defineConfig, devices } from '@playwright/test';

// End-to-end tests against the real stack: the built web behind the SWA
// emulator + API + Azurite. The API has to be running first (html-viewer-api:
// ./start.sh). The web is built and served here, on its own port, so the tests
// always exercise the current code and never touch a dev session on 4280.
export const E2E_PORT = 4281;
export const E2E_URL = `http://localhost:${E2E_PORT}`;

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: true,
  // One local API process sits behind every test.
  workers: 2,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: E2E_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // Tall enough to keep a file and the label it is dragged to on screen together.
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 1000 } } }],
  webServer: {
    command: 'npm run e2e:serve',
    url: E2E_URL,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});

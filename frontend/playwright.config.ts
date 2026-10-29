import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  workers: 1,
  webServer: {
    command: 'python ../scripts/e2e_server.py',
    url: 'http://127.0.0.1:8000/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
  use: { baseURL: 'http://127.0.0.1:8000', browserName: 'chromium', headless: true },
});

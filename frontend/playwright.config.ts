import { defineConfig } from '@playwright/test';
const python = process.env.PAWTEL_E2E_PYTHON;
if (!python || !process.env.PAWTEL_E2E_FIXTURE)
  throw new Error('Use npm run test:e2e so isolated fixture setup runs first.');
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: 'list',
  outputDir: 'e2e-results',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    browserName: 'chromium',
    headless: true,
    reducedMotion: 'reduce',
    screenshot: 'off',
    video: 'off',
    trace: 'off',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn tools.e2e_app:create_e2e_app --factory --host 127.0.0.1 --port 8013 --no-access-log`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8013/ready',
      reuseExistingServer: false,
      timeout: 30_000,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        PAWTEL_API_PROXY_TARGET: 'http://127.0.0.1:8013',
        VITE_STRIPE_PUBLISHABLE_KEY: '',
      },
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
    },
  ],
});

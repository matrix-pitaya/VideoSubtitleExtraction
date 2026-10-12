import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests', testMatch: '*.spec.ts', timeout: 180_000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure', screenshot: 'only-on-failure', acceptDownloads: true },
  reporter: [['list'], ['json', { outputFile: 'artifacts/e2e-results.json' }]],
  projects: [
    { name: 'desktop-edge', use: { browserName: 'chromium', channel: 'msedge' } },
    { name: 'android-emulated', use: { ...devices['Pixel 7'], browserName: 'chromium', channel: 'msedge' } },
    { name: 'iphone-emulated-webkit', use: { ...devices['iPhone 14'], browserName: 'webkit' } },
  ],
});

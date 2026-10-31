import { defineConfig } from '@playwright/test';

// Runs against the built site: `npm run build` first. CI does both in that order.
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  webServer: {
    command: 'node scripts/serve-dist.mjs 4321 127.0.0.1',
    url: 'http://127.0.0.1:4321/',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  // Reduced motion keeps the scan deterministic: nothing is mid-fade when axe measures contrast.
  use: { baseURL: 'http://127.0.0.1:4321', reducedMotion: 'reduce' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});

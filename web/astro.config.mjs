// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// The public address is only known once the domain exists; previews pass their own.
const site = process.env.SITE_URL || 'http://localhost:4321';

export default defineConfig({
  site,
  integrations: [react()],
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});

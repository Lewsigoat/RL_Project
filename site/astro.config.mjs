import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://drillchart.com',
  trailingSlash: 'always',
  integrations: [sitemap()],
});

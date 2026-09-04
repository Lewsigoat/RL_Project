# Deploy, Search Console, AdSense

Static Astro site. Hosting can stay $0/month on Cloudflare Pages.

1. Confirm a domain (candidates: `drillchart.com`, `drillsizechart.com`) at a registrar.
2. Cloudflare Pages → root `site` → `npm run build` → output `dist`.
3. Paste the Search Console HTML token into `src/layouts/Base.astro`.
4. Submit `sitemap-index.xml`.
5. Apply to AdSense after the domain is live; fill `public/ads.txt` with the real `pub-` line.

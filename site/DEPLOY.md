# Deploy, Search Console, AdSense

The site is static. Hosting can stay at $0/month. You still need a domain (~$10–15/year) and a Google account.

## 1. Domain

Likely available (no NS records when checked):

- `pwfitguide.com` (preferred)
- `m22guide.com`
- `washerfit.com`

Buy at Cloudflare Registrar or Porkbun. Do not buy a hyphenated spam domain.

## 2. Email

In Cloudflare, enable Email Routing for `contact@yourdomain`. Update `src/pages/contact.astro` if the address changes.

## 3. Cloudflare Pages

1. Push this repo (or only `site/`) to GitHub.
2. Cloudflare Pages → new project → framework **Astro** → root directory `site` → build `npm run build` → output `dist`.
3. Attach the custom domain. HTTPS is automatic.

Alternative: `npx wrangler pages deploy dist` from `site/` after `npm run build`.

## 4. Google Search Console

1. Add the URL-prefix property `https://pwfitguide.com` (or your domain).
2. Choose the HTML-tag method. Copy the token.
3. Replace `REPLACE_WITH_GSC_TOKEN` in `src/layouts/Base.astro`.
4. Rebuild and redeploy.
5. Submit `https://yoursite/sitemap-index.xml`.
6. Use URL Inspection on `/`, `/identify/`, `/m22-14-vs-15/`, and `/brands/`. Do not bulk-spam inspections.

## 5. AdSense

Do this after the custom domain is live and the 20+ identification pages are reachable.

1. Confirm HTTPS, About, Contact, Privacy, Disclaimer, and a real contact mailbox.
2. Apply at [google.com/adsense](https://www.google.com/adsense/start/) for this exact domain.
3. If approved, paste the AdSense script in `Base.astro` **after** the first-screen answer (not above the H1).
4. Replace the comment in `public/ads.txt` with the official `google.com, pub-…` line Google shows you. Redeploy.
5. Complete tax, identity, and payout settings when AdSense asks. USD payout threshold is $100.

If rejected for “insufficient content,” add another measured brand page or a model-specific note with a source — do not pad word count.

Mediavine-class networks are out of scope until traffic is far past hosting-break-even.

## 6. Kill / double-down

After pages are indexed:

- Impressions on M22 / Sun Joe / adapter queries → write the next page in that cluster.
- Impressions but no clicks → titles are vague; put the size in the title.
- No impressions on the target cluster after a crawl window → the SERP score was wrong; do not bolt a second niche onto this domain.

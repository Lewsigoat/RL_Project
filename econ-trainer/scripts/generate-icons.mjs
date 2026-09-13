import { spawnSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const buildDir = path.join(root, 'build')
const htmlPath = path.join(buildDir, 'icon.html')
const pngPath = path.join(buildDir, 'icon.png')

const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      html, body { margin: 0; width: 1024px; height: 1024px; overflow: hidden; background: #1b2430; }
      svg { display: block; width: 1024px; height: 1024px; }
    </style>
  </head>
  <body>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
      <rect width="64" height="64" rx="14" fill="#1B2430"/>
      <path d="M16 18h22c6 0 10 4 10 9s-4 9-10 9H22v10H16V18zm6 6v6h15c2.6 0 4-1.5 4-3s-1.4-3-4-3H22z" fill="#F3EAD8"/>
      <circle cx="46" cy="46" r="8" fill="#C45C26"/>
    </svg>
  </body>
</html>
`

await mkdir(buildDir, { recursive: true })
await writeFile(htmlPath, html)

const chrome =
  process.env.CHROME_PATH ||
  ['/usr/bin/google-chrome-stable', '/usr/bin/google-chrome', '/usr/bin/chromium'].find((candidate) => {
    const result = spawnSync(candidate, ['--version'], { encoding: 'utf8' })
    return result.status === 0
  })

if (!chrome) {
  throw new Error('Chrome/Chromium is required to rasterize build/icon.png')
}

const result = spawnSync(
  chrome,
  [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    `--screenshot=${pngPath}`,
    '--window-size=1024,1024',
    `file://${htmlPath}`,
  ],
  { encoding: 'utf8' },
)

if (result.status !== 0) {
  console.error(result.stdout)
  console.error(result.stderr)
  throw new Error('Failed to rasterize icon.png')
}

console.log(`Wrote ${pngPath}`)

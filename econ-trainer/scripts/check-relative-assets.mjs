import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const htmlPath = path.join(root, 'dist', 'index.html')
const html = await readFile(htmlPath, 'utf8')

const problems = []
if (!/\.\/assets\//.test(html)) {
  problems.push('dist/index.html has no relative ./assets/ URLs (Vite base should be "./")')
}
if (/ (?:src|href)="\/(?:assets|src)\//.test(html)) {
  problems.push('dist/index.html still has root-absolute asset URLs that break file://')
}

if (problems.length) {
  console.error(html)
  for (const problem of problems) console.error(problem)
  process.exit(1)
}

console.log('Production assets use relative URLs (ok for Electron file://).')

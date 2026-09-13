import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const electronBin = require('electron')
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const port = Number(process.env.VITE_DEV_PORT || 5188)
const devUrl = process.env.VITE_DEV_SERVER_URL || `http://127.0.0.1:${port}`
console.log(`Econ Trainer is on http://localhost:${port} (not 5173)`)

const vite = spawn(process.execPath, [viteBin, '--host', '0.0.0.0', '--port', String(port), '--strictPort'], {
  cwd: root,
  stdio: 'inherit',
})

function waitForVite() {
  return new Promise((resolve, reject) => {
    const started = Date.now()
    const attempt = () => {
      const req = http.get(devUrl, (res) => {
        res.resume()
        resolve()
      })
      req.on('error', () => {
        if (Date.now() - started > 40000) {
          reject(new Error(`Vite did not become ready at ${devUrl}`))
          return
        }
        setTimeout(attempt, 200)
      })
    }
    attempt()
  })
}

function shutdown(code = 0) {
  if (!vite.killed) vite.kill()
  process.exit(code)
}

vite.on('exit', (code) => {
  if (code) shutdown(code)
})

try {
  await waitForVite()
} catch (error) {
  console.error(error instanceof Error ? error.message : error)
  shutdown(1)
}

const electron = spawn(electronBin, ['.'], {
  cwd: root,
  stdio: 'inherit',
  env: {
    ...process.env,
    ELECTRON_DEV: '1',
    VITE_DEV_SERVER_URL: devUrl,
  },
})

const stop = () => {
  if (!electron.killed) electron.kill()
  if (!vite.killed) vite.kill()
}

process.on('SIGINT', stop)
process.on('SIGTERM', stop)

electron.on('exit', (code) => {
  if (!vite.killed) vite.kill()
  process.exit(code ?? 0)
})

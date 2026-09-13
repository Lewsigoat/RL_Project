import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

/** Dedicated port — 5173 is commonly taken by other Vite apps (e.g. Neon Country). */
const TRAINER_PORT = 5188

function openHint(): Plugin {
  return {
    name: 'econ-trainer-open-hint',
    configureServer(server) {
      server.httpServer?.once('listening', () => {
        server.config.logger.info('')
        server.config.logger.info('  Econ Trainer is running. Open this URL on THIS computer:')
        server.config.logger.info(`  http://localhost:${TRAINER_PORT}`)
        server.config.logger.info('  Leave this terminal open. Closing it stops the site.')
        server.config.logger.info('  http://localhost:5173 is Neon Country — not this app.')
        server.config.logger.info('  Opening 5188 without this command will not load.')
        server.config.logger.info('')
      })
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), openHint()],
  server: {
    host: true,
    port: TRAINER_PORT,
    strictPort: true,
    // Cursor / cloud previews send a hostname, not localhost. Vite 8 blocks those by default (403).
    allowedHosts: true,
  },
  preview: {
    host: true,
    port: TRAINER_PORT,
    strictPort: true,
    allowedHosts: true,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})

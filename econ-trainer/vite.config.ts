import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

/** Dedicated port — 5173 is commonly taken by other Vite apps (e.g. Neon Country). */
const TRAINER_PORT = 5188

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: true,
    port: TRAINER_PORT,
    strictPort: true,
  },
  preview: {
    host: true,
    port: TRAINER_PORT,
    strictPort: true,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})

import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
// vitest/config rather than vite: it is the export whose type includes the
// `test` block below.
import { defineConfig } from 'vitest/config'

// The dev server proxies /api to the backend container so the browser only ever
// talks to one origin. That keeps development on the same relative URLs the
// nginx build serves in production, rather than a localhost:8000 that only
// works on one machine.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})

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
    // Gated for the same reason the backend is: without a threshold, five
    // pages sat untested and nothing in CI could tell. Thresholds are set at
    // what the suite actually reaches, rounded down — an aspirational number
    // that always fails teaches everyone to ignore it.
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
      ],
      thresholds: { lines: 90, functions: 85, branches: 90, statements: 90 },
    },
  },
})

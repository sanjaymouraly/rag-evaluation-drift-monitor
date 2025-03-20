import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

declare const process: any

// The dev/preview server proxies /api and /health to the FastAPI backend so the
// browser only ever talks to the Vite origin. Override with VITE_API_TARGET
// (Docker Compose sets VITE_API_TARGET=http://backend:8000).
const apiTarget =
  (typeof process !== 'undefined' && process.env?.VITE_API_TARGET) || 'http://127.0.0.1:8000'

const proxy = {
  '/api': {
    target: apiTarget,
    changeOrigin: true,
  },
  '/health': {
    target: apiTarget,
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Vite 6+ host allowlist; harmless on Vite 5 (preview proxy needs any host).
    ...({ allowedHosts: true } as Record<string, unknown>),
    proxy,
  },
  preview: { host: '0.0.0.0', port: 5173, proxy },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})

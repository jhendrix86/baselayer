import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Backend the dev server proxies /api, /health, /metrics to.
// Default is the local dev backend; override to run against a remote
// (e.g. the live Nexus stack) without editing this file:
//   VITE_API_TARGET=http://100.91.161.114:8000 pnpm dev
// or, if that host's :8000 isn't reachable directly, tunnel it first:
//   ssh -N -L 8000:localhost:8000 nexus   # then leave the default
const API_TARGET =
  process.env.VITE_API_TARGET ||
  loadEnv('', process.cwd(), 'VITE_').VITE_API_TARGET ||
  'http://localhost:8000'

const proxyEntry = { target: API_TARGET, changeOrigin: true, secure: false }

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/pages': path.resolve(__dirname, './src/pages'),
      '@/hooks': path.resolve(__dirname, './src/hooks'),
      '@/utils': path.resolve(__dirname, './src/utils'),
      '@/types': path.resolve(__dirname, './src/types'),
      '@/store': path.resolve(__dirname, './src/store'),
      '@/api': path.resolve(__dirname, './src/api'),
      '@/assets': path.resolve(__dirname, './src/assets'),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': { ...proxyEntry },
      '/health': { ...proxyEntry },
      '/metrics': { ...proxyEntry },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom'],
          query: ['@tanstack/react-query'],
          ui: ['@headlessui/react', 'lucide-react'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
  },
})

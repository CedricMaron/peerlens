import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During native development the API runs separately on :8000.
// In production FastAPI serves this build itself, so the proxy is unused.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  build: { outDir: 'dist', sourcemap: false },
})

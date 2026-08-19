import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During native development the API runs separately, by default on :8000.
// `run.sh` honours PEERLENS_PORT when 8000 is taken, so follow it here too.
// In production FastAPI serves this build itself, so the proxy is unused.
const apiPort = process.env.PEERLENS_PORT || '8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: `http://localhost:${apiPort}`, changeOrigin: true } },
  },
  build: { outDir: 'dist', sourcemap: false },
})

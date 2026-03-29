import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // VITE_BASE_PATH is injected at Docker build time (e.g. /svc/vibe2/).
  // Unset in dev (npm run dev) — dev server proxy handles /api directly.
  base: process.env.VITE_BASE_PATH || '/',
  server: {
    port: 3002,
    proxy: {
      '/api': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})

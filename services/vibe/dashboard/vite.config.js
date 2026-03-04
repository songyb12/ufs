import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/ui/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/dashboard': 'http://localhost:8001',
      '/signals': 'http://localhost:8001',
      '/portfolio': 'http://localhost:8001',
      '/pipeline': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
      '/watchlist': 'http://localhost:8001',
      '/risk': 'http://localhost:8001',
      '/backtest': 'http://localhost:8001',
      '/sentiment': 'http://localhost:8001',
    },
  },
})

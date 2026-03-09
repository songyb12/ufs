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
      '/alerts': 'http://localhost:8001',
      '/briefing': 'http://localhost:8001',
      '/settings': 'http://localhost:8001',
      '/admin': 'http://localhost:8001',
      '/screening': 'http://localhost:8001',
      '/data': 'http://localhost:8001',
      '/macro-intel': 'http://localhost:8001',
      '/guru': 'http://localhost:8001',
      '/action-plan': 'http://localhost:8001',
      '/academy': 'http://localhost:8001',
      '/notifications': 'http://localhost:8001',
      '/auth': 'http://localhost:8001',
    },
  },
})

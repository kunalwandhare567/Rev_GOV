import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
    // Force a single copy of React to fix React 19 + Zustand v5 hook error
    dedupe: ['react', 'react-dom', 'react-router-dom'],
  },
})



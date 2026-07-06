import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/analyze-submission': 'http://localhost:8000',
      '/viva-session': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': BACKEND,
      '/media': BACKEND,
      '/ws': { target: BACKEND.replace(/^http/, 'ws'), ws: true },
    },
  },
})

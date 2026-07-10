import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // emit into the Python package so `pip install .` ships the UI
    outDir: '../backend/dmarcayn/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // dev mode: the Python backend serves the API
      '/api': 'http://127.0.0.1:8080',
    },
  },
})

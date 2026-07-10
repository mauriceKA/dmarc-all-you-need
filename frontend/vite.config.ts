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
    rolldownOptions: {
      output: {
        // split the two heavyweight vendor trees into their own chunks:
        // keeps every chunk well under the 500 kB warning threshold and
        // lets browsers cache vendors across app updates
        codeSplitting: {
          groups: [
            { name: 'recharts', test: /node_modules[\\/](recharts|d3-|victory-vendor|internmap|delaunator|robust-predicates)/ },
            { name: 'react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      // dev mode: the Python backend serves the API
      '/api': 'http://127.0.0.1:8080',
    },
  },
})

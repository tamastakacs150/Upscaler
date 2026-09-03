// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    // A Flask a static/app alol szolgalja ki az SPA-t (app.py), ezert
    // kozvetlenul oda epitunk - kulon masolasi lepes nelkul.
    outDir: path.resolve(__dirname, '../static/app'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:7860',
      '/uploads': 'http://localhost:7860',
      '/outputs': 'http://localhost:7860',
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build vai para src/api/dist para o FastAPI servir. Dev usa proxy p/ a API.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../backend/src/api/dist', emptyOutDir: true },
  server: { proxy: { '/api': 'http://localhost:8010' } },
})

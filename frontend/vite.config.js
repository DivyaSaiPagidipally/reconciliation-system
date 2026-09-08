import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: Vite on :5174, Django API on :8000 — proxy /api to avoid CORS.
// Use 127.0.0.1 explicitly: `localhost` may resolve to ::1 while Django
// binds IPv4 by default.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
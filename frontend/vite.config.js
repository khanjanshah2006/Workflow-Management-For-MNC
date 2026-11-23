import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBaseUrl = env.VITE_API_BASE_URL || process.env.VITE_API_BASE_URL

  if (mode === 'production' && !apiBaseUrl) {
    throw new Error(
      'VITE_API_BASE_URL environment variable must be set for production builds.'
    )
  }

  return {
    plugins: [react()],
  }
})

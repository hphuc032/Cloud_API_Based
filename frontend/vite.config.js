import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.API_PROXY_TARGET || 'http://127.0.0.1:8000'
  const proxy = {
    target: backendTarget,
    changeOrigin: true,
    secure: true,
    headers: { 'ngrok-skip-browser-warning': 'true' },
  }
  return {
    plugins: [react()],
    server: { port: 5173, proxy: { '/api': proxy, '/health': proxy } },
  }
})

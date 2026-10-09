import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.API_PROXY_TARGET || 'https://localhost:8443'
  const proxy = {
    target: backendTarget,
    changeOrigin: true,
    secure: true,
    headers: { 'ngrok-skip-browser-warning': 'true' },
  }
  return {
    plugins: [react()],
    server: { https: env.VITE_TLS_CERT && env.VITE_TLS_KEY ? {cert:readFileSync(env.VITE_TLS_CERT),key:readFileSync(env.VITE_TLS_KEY)} : undefined, port: 5173, proxy: { '/api': proxy, '/health': proxy } },
  }
})

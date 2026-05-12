import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/preview': {
        target: 'http://workspace:3000',
        changeOrigin: false,
        ws: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('host', 'localhost')
          })
          proxy.on('proxyReqWs', (proxyReq) => {
            proxyReq.setHeader('host', 'localhost')
          })
        },
      },
    },
  },
})

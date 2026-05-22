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
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        configure: (proxy: any) => {
          proxy.on('proxyReq', (proxyReq: any) => {
            proxyReq.setHeader('host', 'localhost')
          })
          proxy.on('proxyReqWs', (proxyReq: any) => {
            proxyReq.setHeader('host', 'localhost')
          })
        },
      },
    },
  },
})

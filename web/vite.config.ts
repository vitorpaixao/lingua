import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      // Real backend (production: nginx does this; dev: Vite proxy)
      '/api': {
        target: process.env.LINGUA_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
      '/preview': {
        target: process.env.LINGUA_PREVIEW_TARGET ?? 'http://localhost:3000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/preview/, ''),
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
  },
});

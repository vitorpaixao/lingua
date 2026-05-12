// Auto-loaded by the workspace container so Vite trusts the proxy host
// from the web container ("workspace") and exposes HMR through /preview.
import { mergeConfig, loadConfigFromFile } from 'vite'
import { resolve } from 'node:path'
import { existsSync } from 'node:fs'

const cwd = process.cwd()
const candidates = ['vite.config.ts', 'vite.config.js', 'vite.config.mjs', 'vite.config.mts']
let base = {}
for (const name of candidates) {
  const p = resolve(cwd, name)
  if (existsSync(p)) {
    const loaded = await loadConfigFromFile(
      { command: 'serve', mode: 'development' },
      p,
    )
    if (loaded?.config) {
      base = loaded.config
      break
    }
  }
}

export default mergeConfig(base, {
  base: '/preview/',
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: true,
    hmr: {
      clientPort: 5173,
      path: '/preview/',
    },
  },
})

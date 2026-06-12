import { defineConfig, loadConfigFromFile } from 'vite';
import path from 'node:path';

// Lingua-owned Vite config override. Loaded via `vite --config` from the
// workspace entrypoint so we don't need to touch the bootstrap repo's own
// vite.config.{ts,js}. We extend the user's config and force:
//   - base=/preview/  so HTML asset URLs are routed through the nginx proxy
//   - HMR WebSocket pointing back at the host's public port (5173) and the
//     nginx /preview/ path
//   - allowedHosts=true since we're behind a reverse proxy

export default defineConfig(async ({ mode }) => {
  const projectRoot = process.cwd();
  let userConfig = {};

  for (const fname of ['vite.config.ts', 'vite.config.js', 'vite.config.mjs']) {
    try {
      const loaded = await loadConfigFromFile(
        { command: 'serve', mode },
        path.join(projectRoot, fname),
      );
      if (loaded) {
        userConfig = loaded.config;
        break;
      }
    } catch {
      // try next filename
    }
  }

  return {
    ...userConfig,
    base: '/preview/',
    server: {
      ...(userConfig.server ?? {}),
      host: '0.0.0.0',
      port: 3000,
      strictPort: true,
      hmr: {
        host: 'localhost',
        clientPort: 5173,
        path: '/preview/',
        protocol: 'ws',
      },
      allowedHosts: true,
    },
  };
});

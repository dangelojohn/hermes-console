import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Hermes Console UI - Vite config.
// Dev server proxies /api → the sibling API service so we can develop without CORS headaches.
// Build output: dist/ (consumed by the nginx stage of the Dockerfile).
// Service worker lives at src/sw.js (single source of truth); we publish it to /sw.js in
// both dev (middleware) and prod (emitted asset).
function serviceWorkerPlugin() {
  const swPath = resolve(__dirname, 'src/sw.js');
  return {
    name: 'hermes-sw',
    configureServer(server) {
      server.middlewares.use('/sw.js', (_req, res) => {
        res.setHeader('content-type', 'application/javascript');
        res.setHeader('cache-control', 'no-cache');
        res.end(readFileSync(swPath, 'utf8'));
      });
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: readFileSync(swPath, 'utf8'),
      });
    },
  };
}

export default defineConfig({
  plugins: [vue(), serviceWorkerPlugin()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.HERMES_API_URL || 'http://hermes-api:8000',
        changeOrigin: true,
        ws: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    target: 'es2020',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
});

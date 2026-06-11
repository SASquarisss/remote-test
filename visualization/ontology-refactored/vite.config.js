import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9120',
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      input: {
        workspace: resolve(__dirname, 'index.html'),
        database: resolve(__dirname, 'index.database.html')
      }
    }
  }
});

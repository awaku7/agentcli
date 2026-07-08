import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import path from 'path';

export default defineConfig({
  plugins: [svelte()],
  root: '.',
  base: '/static/',
  build: {
    outDir: path.resolve(__dirname, '..', 'src', 'uagent', 'static'),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/upload': 'http://localhost:8000',
      '/local-file': 'http://localhost:8000',
    },
  },
});

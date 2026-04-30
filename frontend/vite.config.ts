import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    // Proxy API requests to backend
    // Use 'app' for Docker, 'localhost' for local dev
    proxy: {
      '/api': {
        target: process.env.API_URL || 'http://app:8000',
        changeOrigin: true
      }
    }
  }
});

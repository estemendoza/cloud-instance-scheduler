import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Preprocess with Vite (handles TypeScript, PostCSS)
  preprocess: vitePreprocess(),

  kit: {
    // Static adapter for SPA mode
    adapter: adapter({
      // Output to 'build' directory
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',  // SPA fallback for client-side routing
      precompress: false,
      strict: true
    })
  }
};

export default config;

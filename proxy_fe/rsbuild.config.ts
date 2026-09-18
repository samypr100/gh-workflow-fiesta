import { defineConfig } from '@rsbuild/core';
import { pluginVue } from '@rsbuild/plugin-vue';
import { pluginTailwindcss } from '@rsbuild/plugin-tailwindcss';

// In production the app is served from a path prefix on an existing zone
// rather than from its own hostname, so the bundle's own asset URLs and its
// API calls must both carry that prefix. Locally both are empty and the API
// lives on a separate port.
//
// PUBLIC_BASE_PATH must match the route pattern in wrangler.jsonc.
const basePath = process.env.PUBLIC_BASE_PATH ?? '';
const apiUrl = process.env.PUBLIC_API_URL ?? (basePath || 'http://localhost:8000');

// Docs: https://rsbuild.rs/config/
export default defineConfig({
  plugins: [pluginVue(), pluginTailwindcss()],
  server: {
    port: 3000,
  },
  output: {
    // Trailing slash matters: without it the emitted URLs are siblings of the
    // prefix rather than children of it.
    assetPrefix: basePath === '' ? '/' : `${basePath}/`,
  },
  source: {
    define: {
      'process.env.PUBLIC_API_URL': JSON.stringify(apiUrl),
    },
  },
});

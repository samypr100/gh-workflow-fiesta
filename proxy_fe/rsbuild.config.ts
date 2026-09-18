import { defineConfig } from '@rsbuild/core';
import { pluginVue } from '@rsbuild/plugin-vue';
import { pluginTailwindcss } from '@rsbuild/plugin-tailwindcss';

// Docs: https://rsbuild.rs/config/
export default defineConfig({
  plugins: [pluginVue(), pluginTailwindcss()],
  server: {
    port: 3000,
  },
  source: {
    define: {
      'process.env.PUBLIC_API_URL': JSON.stringify(
        process.env.PUBLIC_API_URL ?? 'http://localhost:8000',
      ),
    },
  },
});

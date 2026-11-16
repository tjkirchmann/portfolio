// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import { satteri } from '@astrojs/markdown-satteri';
import { figurePlugin } from './src/lib/figure-plugin.mjs';
import { chaferTheme } from './src/lib/shiki-theme.mjs';

export default defineConfig({
  site: 'https://example.com',
  output: 'static',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  image: {
    layout: 'constrained',
    responsiveStyles: false,
    breakpoints: [360, 480, 640, 960, 1280],
  },
  markdown: {
    processor: satteri({ hastPlugins: [figurePlugin] }),
    shikiConfig: { theme: chaferTheme, wrap: false },
  },
  devToolbar: { enabled: false },
  vite: { plugins: [tailwindcss()] },
});

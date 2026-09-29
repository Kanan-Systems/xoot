/// <reference types="vitest/config" />
// The build writes the committed bundle the Python package serves. Nothing
// may be inlined: the CSP allows scripts, styles and fonts from 'self' only.
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: '../src/xoot/dashboard/static',
    emptyOutDir: true,
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    sourcemap: false,
    // Keep one entry chunk per build so the committed diff stays small.
    chunkSizeWarningLimit: 1024,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});

/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // Sibling of this directory, not nested inside it -- matches exactly
    // what webapp/app.py's StaticFiles mount and SPA-fallback handler
    // point at.
    outDir: '../frontend_dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
})

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
    rollupOptions: {
      output: {
        // frontend_dist/ is committed (this webapp runs from a bare
        // clone via nohup+uvicorn, with no CI/deploy build step) --
        // Vite's default content-hashed filenames mean every rebuild
        // adds new tracked files rather than modifying existing ones,
        // so a rebuild-and-commit that forgets to `git add -A` (only
        // stages index.html, or only the new asset) leaves a
        // committed index.html pointing at a bundle that was never
        // added, or an orphaned old bundle nothing references anymore.
        // Stable names mean every rebuild modifies the same paths in
        // place instead.
        // [name] alone (no hash) means two assets that ever end up with
        // the same base name would silently collide -- not a concern for
        // this app's current asset set (checked: the vendored Geist font
        // subsets already have distinct names), but worth knowing if a
        // future asset addition needs a name check.
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
})

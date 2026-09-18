import path from "node:path"
import react from "@vitejs/plugin-react"
import { configDefaults, defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/vitest-setup.ts"],
    // vitest's own default `include` glob (**/*.{test,spec}.*) has no way
    // to tell a Playwright spec apart from one of its own -- without this,
    // it picks up frontend/e2e/interconnected-ui.spec.ts (Task 16) and
    // tries to execute @playwright/test's own `test()` under vitest's
    // runner instead, which fails immediately with "Playwright Test did
    // not expect test() to be called here" (confirmed live). `playwright
    // test`'s own `testDir: "./e2e"` in playwright.config.ts is already
    // the one and only runner for that directory.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
})

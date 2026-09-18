import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:8021" },
  webServer: {
    command: "cd .. && python3 -m uvicorn --factory --app-dir . webapp.main:_e2e_app --host 127.0.0.1 --port 8021",
    url: "http://127.0.0.1:8021",
    reuseExistingServer: false,
    timeout: 120_000,
  },
})

import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirror tsconfig's "@/*": ["./*"] so component imports and vi.mock
    // specifiers resolve to the same module ids.
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    environment: "jsdom",
    globals: true, // required for @testing-library/react auto-cleanup
    setupFiles: ["./vitest.setup.ts"],
  },
})

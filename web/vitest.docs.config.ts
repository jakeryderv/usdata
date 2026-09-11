import { cloudflareTest } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: { include: ["test/docs.test.ts"] },
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "../docs/hosting/wrangler.jsonc" },
    }),
  ],
});

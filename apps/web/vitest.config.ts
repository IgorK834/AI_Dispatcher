import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      // context.md → Testing Standards: web `lib/` at least 80 % (lines and branches), enforced
      // by `pnpm --filter web test:coverage`. The generated API schema holds types only.
      include: ['src/lib/**'],
      exclude: ['src/lib/**/*.test.{ts,tsx}', 'src/lib/api/schema.d.ts'],
      reporter: ['text'],
      thresholds: { lines: 80, branches: 80 },
    },
  },
});

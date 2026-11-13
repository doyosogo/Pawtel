import { readFileSync } from 'node:fs';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig(({ mode }) => ({
  // Read only VITE_-prefixed public values from the existing root .env.
  // Server-only database/Stripe secrets are never exposed through import.meta.env.
  envDir: mode === 'showcase' ? '.' : '..',
  preview: {
    headers:
      mode === 'showcase'
        ? Object.fromEntries(
            (
              JSON.parse(
                readFileSync(new URL('./vercel.json', import.meta.url), 'utf8'),
              ).headers[0].headers as { key: string; value: string }[]
            ).map(({ key, value }) => [key, value]),
          )
        : undefined,
  },
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.PAWTEL_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    clearMocks: true,
  },
}));

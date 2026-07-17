/// <reference types="vitest/config" />
import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// Env lives at the repo root so client and server share a single .env file.
const repoRoot = path.resolve(import.meta.dirname, '..');

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, repoRoot, 'PRECEDENT_'), ...process.env };
  const serverPort = env.PRECEDENT_PORT ?? '8000';

  return {
    plugins: [react(), tailwindcss()],
    envDir: repoRoot,
    server: {
      // 127.0.0.1 rather than localhost: Node on Windows can resolve
      // localhost to ::1 while the API server binds IPv4 only.
      proxy: {
        '/api': `http://127.0.0.1:${serverPort}`,
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  };
});

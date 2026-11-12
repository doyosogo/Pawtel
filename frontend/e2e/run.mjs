import { spawn } from 'node:child_process';
import { mkdir, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../../', import.meta.url));
const python =
  process.env.PAWTEL_E2E_PYTHON || path.join(root, 'backend/.venv/bin/python');
const fixture = path.join(
  root,
  '.cache',
  `e2e-${process.pid}-${Date.now()}.json`,
);
const env = {
  ...process.env,
  APP_ENV: 'test',
  DATABASE_URL: process.env.E2E_DATABASE_URL || '',
  PAWTEL_E2E_FIXTURE: fixture,
  PAWTEL_E2E_PYTHON: python,
  PLAYWRIGHT_BROWSERS_PATH: path.join(root, '.cache/pw-browsers'),
  STRIPE_SECRET_KEY: '',
  STRIPE_WEBHOOK_SECRET: '',
  CLOUDINARY_API_KEY: '',
  CLOUDINARY_API_SECRET: '',
};
if (!env.E2E_DATABASE_URL)
  throw new Error(
    'Set E2E_DATABASE_URL for the dedicated pawtel_e2e database.',
  );
await mkdir(path.dirname(fixture), { recursive: true });
let child;
function run(cmd, args, cwd) {
  return new Promise((resolve) => {
    child = spawn(cmd, args, { cwd, env, stdio: 'inherit' });
    child.on('error', () => resolve(1));
    child.on('exit', (code) => resolve(code ?? 1));
  });
}
process.on('SIGINT', () => child?.kill('SIGINT'));
process.on('SIGTERM', () => child?.kill('SIGTERM'));
let result = 1;
try {
  const setup = await run(
    python,
    ['-m', 'tools.e2e_data', 'setup', fixture],
    path.join(root, 'backend'),
  );
  if (setup === 0)
    result = await run(
      process.execPath,
      [
        path.join(root, 'frontend/node_modules/@playwright/test/cli.js'),
        'test',
        '--config',
        'playwright.config.ts',
      ],
      path.join(root, 'frontend'),
    );
} finally {
  if (await stat(fixture).catch(() => null)) {
    const cleaned = await run(
      python,
      ['-m', 'tools.e2e_data', 'cleanup', fixture],
      path.join(root, 'backend'),
    );
    if (cleaned !== 0) result = 1;
  }
}
process.exitCode = result;

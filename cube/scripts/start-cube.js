'use strict';

const path = require('path');
const { spawn } = require('child_process');
const { runStartupDiagnostics } = require('../lib/diagnostics');

const CONF_ROOT = path.join(__dirname, '..');

async function main() {
  let diagnosticsFailed = false;
  try {
    const result = await runStartupDiagnostics(CONF_ROOT);
    if (!result.db.ok) diagnosticsFailed = true;
    if (result.layout.files.length === 0) diagnosticsFailed = true;
  } catch (err) {
    console.error('[mrmed-cube] Diagnostics threw:', err);
    diagnosticsFailed = true;
  }

  if (diagnosticsFailed && process.env.CUBEJS_STRICT_STARTUP === 'true') {
    console.error(
      '[mrmed-cube] Exiting (CUBEJS_STRICT_STARTUP=true). Fix env/schema/DB and redeploy.'
    );
    process.exit(1);
  }

  if (diagnosticsFailed) {
    console.warn(
      '[mrmed-cube] Starting cubejs-server anyway — check Cloud Run logs for errors above.'
    );
  }

  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['cubejs-server'],
    {
      cwd: CONF_ROOT,
      stdio: 'inherit',
      env: {
        ...process.env,
        CUBEJS_LOG_LEVEL: process.env.CUBEJS_LOG_LEVEL || 'info',
      },
    }
  );

  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code ?? 1);
  });
}

main().catch((err) => {
  console.error('[mrmed-cube] Fatal startup error:', err);
  process.exit(1);
});

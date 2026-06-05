'use strict';

const fs = require('fs');
const path = require('path');

const LOG_PREFIX = '[mrmed-cube]';

function log(level, message, extra) {
  const line = {
    ts: new Date().toISOString(),
    level,
    message,
    ...(extra && Object.keys(extra).length ? { extra } : {}),
  };
  const out = `${LOG_PREFIX} ${JSON.stringify(line)}`;
  if (level === 'error') {
    console.error(out);
  } else {
    console.log(out);
  }
}

function maskSecret(value) {
  if (value == null || value === '') return '(empty)';
  const s = String(value);
  if (s.length <= 4) return '****';
  return `${s.slice(0, 2)}…${s.slice(-2)} (${s.length} chars)`;
}

function logEnvironment() {
  const keys = [
    'NODE_ENV',
    'PORT',
    'K_SERVICE',
    'K_REVISION',
    'CUBEJS_DEV_MODE',
    'CUBEJS_LOG_LEVEL',
    'CUBEJS_SCHEMA_PATH',
    'CUBEJS_DB_TYPE',
    'CUBEJS_DB_HOST',
    'CUBEJS_DB_PORT',
    'CUBEJS_DB_NAME',
    'CUBEJS_DB_USER',
    'CUBEJS_DB_SSL',
    'CUBEJS_DB_SSL_REJECT_UNAUTHORIZED',
  ];
  const env = {};
  for (const key of keys) {
    env[key] = process.env[key] ?? '(unset)';
  }
  env.CUBEJS_DB_PASS = maskSecret(process.env.CUBEJS_DB_PASS);
  env.CUBEJS_API_SECRET = maskSecret(process.env.CUBEJS_API_SECRET);
  log('info', 'Environment snapshot', env);
  log('info', 'Process paths', {
    cwd: process.cwd(),
    dirname: __dirname,
    nodeVersion: process.version,
  });
}

function listDirRecursive(dir, base = '') {
  if (!fs.existsSync(dir)) return [];
  const entries = [];
  for (const name of fs.readdirSync(dir)) {
    const rel = base ? `${base}/${name}` : name;
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) {
      entries.push(...listDirRecursive(full, rel));
    } else {
      entries.push({ path: rel, bytes: stat.size });
    }
  }
  return entries;
}

function ensureModelFromSchema(confRoot) {
  const schemaDir = path.join(confRoot, 'schema');
  const modelDir = path.join(confRoot, 'model');
  if (fs.existsSync(modelDir)) {
    return { action: 'exists', modelDir };
  }
  if (!fs.existsSync(schemaDir)) {
    return { action: 'missing_both', schemaDir, modelDir };
  }
  fs.cpSync(schemaDir, modelDir, { recursive: true });
  return { action: 'copied_schema_to_model', schemaDir, modelDir };
}

function auditSchemaLayout(confRoot) {
  const schemaPath = process.env.CUBEJS_SCHEMA_PATH || 'model';
  const resolved = path.resolve(
    path.isAbsolute(schemaPath) ? schemaPath : path.join(confRoot, schemaPath)
  );
  const ensure = ensureModelFromSchema(confRoot);
  log('info', 'Schema directory bootstrap', {
    schemaPathEnv: schemaPath,
    resolved,
    ensure,
  });
  const files = listDirRecursive(resolved).filter((f) =>
    /\.(js|yml|yaml|jinja|py)$/i.test(f.path)
  );
  log('info', 'Schema files on disk', {
    count: files.length,
    files: files.map((f) => f.path),
  });
  if (files.length === 0) {
    log('error', 'No schema files found — /meta will return empty cubes', {
      resolved,
      hint: 'Dockerfile should run: cp -a schema model',
    });
  }
  return { resolved, files, ensure };
}

async function testDatabaseConnection() {
  const host = process.env.CUBEJS_DB_HOST;
  const port = process.env.CUBEJS_DB_PORT;
  const database = process.env.CUBEJS_DB_NAME;
  const user = process.env.CUBEJS_DB_USER;
  const password = process.env.CUBEJS_DB_PASS;
  if (!host || !database || !user) {
    log('error', 'Database env incomplete — skipping connection test', {
      hasHost: !!host,
      hasDatabase: !!database,
      hasUser: !!user,
    });
    return { ok: false, reason: 'incomplete_env' };
  }
  try {
    const { Client } = require('pg');
    const sslEnabled =
      String(process.env.CUBEJS_DB_SSL || '').toLowerCase() === 'true';
    const rejectUnauthorized =
      String(
        process.env.CUBEJS_DB_SSL_REJECT_UNAUTHORIZED || 'false'
      ).toLowerCase() === 'true';
    const client = new Client({
      host,
      port: port ? Number(port) : 5432,
      database,
      user,
      password,
      ssl: sslEnabled ? { rejectUnauthorized } : undefined,
      connectionTimeoutMillis: 15000,
    });
    await client.connect();
    const version = await client.query('SELECT version()');
    const medicines = await client.query(
      'SELECT COUNT(*)::int AS n FROM medicines'
    );
    await client.end();
    log('info', 'Database connection test OK', {
      host,
      port: port || 5432,
      database,
      ssl: sslEnabled,
      rejectUnauthorized: sslEnabled ? rejectUnauthorized : null,
      pgVersion: version.rows[0]?.version?.slice(0, 60),
      medicinesCount: medicines.rows[0]?.n,
    });
    return { ok: true, medicinesCount: medicines.rows[0]?.n };
  } catch (err) {
    log('error', 'Database connection test FAILED', {
      message: err.message,
      code: err.code,
      hint:
        err.code === 'ENOTFOUND'
          ? 'Check CUBEJS_DB_HOST (use Railway public host, not postgres.railway.internal)'
          : err.code === '28P01'
            ? 'Wrong CUBEJS_DB_PASS'
            : 'For Railway public URL use port 25478 and CUBEJS_DB_SSL=true',
    });
    return { ok: false, error: err.message, code: err.code };
  }
}

async function runStartupDiagnostics(confRoot) {
  log('info', '=== MrMed Cube startup diagnostics ===');
  logEnvironment();
  const layout = auditSchemaLayout(confRoot);
  const db = await testDatabaseConnection();
  log('info', '=== Diagnostics complete ===', {
    schemaFileCount: layout.files.length,
    dbOk: db.ok,
  });
  return { layout, db };
}

module.exports = {
  LOG_PREFIX,
  log,
  logEnvironment,
  auditSchemaLayout,
  ensureModelFromSchema,
  testDatabaseConnection,
  runStartupDiagnostics,
};

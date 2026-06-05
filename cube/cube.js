const path = require('path');
const fs = require('fs');
const { FileRepository } = require('@cubejs-backend/shared');
const { PostgresDriver } = require('@cubejs-backend/postgres-driver');
const { log, ensureModelFromSchema } = require('./lib/diagnostics');

const CONF_ROOT = __dirname;
const SCHEMA_PATH = process.env.CUBEJS_SCHEMA_PATH || 'model';

// Safety net: production image uses Dockerfile cp; local dev often only has schema/
ensureModelFromSchema(CONF_ROOT);

function cubeLogger(msg, params) {
  log('cube', msg, params && typeof params === 'object' ? params : { detail: params });
}

module.exports = {
  schemaPath: SCHEMA_PATH,
  // Single Cloud Run instance — no separate Cube Store service
  cacheAndQueueDriver: process.env.CUBEJS_CACHE_AND_QUEUE_DRIVER || 'memory',

  logger: cubeLogger,

  repositoryFactory: () => {
    const repo = new FileRepository(SCHEMA_PATH);
    const original = repo.dataSchemaFiles.bind(repo);
    repo.dataSchemaFiles = async (includeDependencies = false) => {
      const files = await original(includeDependencies);
      log('info', 'Cube repository loaded schema files', {
        schemaPath: SCHEMA_PATH,
        localPath: repo.localPath(),
        count: files.length,
        fileNames: files.map((f) => f.fileName),
      });
      if (files.length === 0) {
        log('error', 'Repository returned zero files — meta will be empty', {
          localPath: repo.localPath(),
          cwd: process.cwd(),
          modelExists: fs.existsSync(path.join(CONF_ROOT, 'model')),
          schemaExists: fs.existsSync(path.join(CONF_ROOT, 'schema')),
        });
      }
      return files;
    };
    return repo;
  },

  driverFactory: async () => {
    log('info', 'Creating PostgresDriver', {
      host: process.env.CUBEJS_DB_HOST,
      port: process.env.CUBEJS_DB_PORT,
      database: process.env.CUBEJS_DB_NAME,
      ssl: process.env.CUBEJS_DB_SSL,
    });
    const driver = new PostgresDriver();
    try {
      await driver.testConnection();
      log('info', 'PostgresDriver.testConnection() succeeded');
    } catch (err) {
      log('error', 'PostgresDriver.testConnection() failed', {
        message: err.message,
        code: err.code,
      });
      throw err;
    }
    return driver;
  },

};

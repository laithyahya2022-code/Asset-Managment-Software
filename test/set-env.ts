// Runs before any module import: tests use the in-memory sql.js driver so
// the full platform boots with zero external services.
process.env.DB_TYPE = 'sqljs';
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'test-access-secret';
process.env.JWT_REFRESH_SECRET = 'test-refresh-secret';
process.env.BCRYPT_ROUNDS = '4';
process.env.THROTTLE_LIMIT = '10000';

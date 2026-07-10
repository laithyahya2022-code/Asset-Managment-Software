/** E2E suite: boots the full application against an in-memory database. */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  rootDir: '.',
  testMatch: ['<rootDir>/test/**/*.e2e-spec.ts'],
  setupFiles: ['<rootDir>/test/set-env.ts'],
  testTimeout: 60000,
  maxWorkers: 1,
};

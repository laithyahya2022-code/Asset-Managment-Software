/**
 * Centralised, typed application configuration.
 *
 * Every value can be overridden through environment variables so the same
 * build artifact can be promoted across environments (12-factor).
 */
export interface AppConfig {
  env: string;
  port: number;
  globalPrefix: string;
  database: {
    /** 'postgres' for real deployments, 'sqljs' for local demos / e2e tests */
    type: 'postgres' | 'sqljs';
    host: string;
    port: number;
    username: string;
    password: string;
    name: string;
    /** Schema sync is for development only — use migrations in production. */
    synchronize: boolean;
    logging: boolean;
    ssl: boolean;
  };
  jwt: {
    secret: string;
    accessTtl: string;
    refreshSecret: string;
    refreshTtl: string;
  };
  throttle: {
    ttlMs: number;
    limit: number;
  };
  security: {
    bcryptRounds: number;
  };
}

export default (): AppConfig => ({
  env: process.env.NODE_ENV ?? 'development',
  port: parseInt(process.env.PORT ?? '3000', 10),
  globalPrefix: process.env.API_PREFIX ?? 'api/v1',
  database: {
    type: (process.env.DB_TYPE as 'postgres' | 'sqljs') ?? 'postgres',
    host: process.env.DB_HOST ?? 'localhost',
    port: parseInt(process.env.DB_PORT ?? '5432', 10),
    username: process.env.DB_USERNAME ?? 'itam',
    password: process.env.DB_PASSWORD ?? 'itam',
    name: process.env.DB_NAME ?? 'itam',
    synchronize: (process.env.DB_SYNCHRONIZE ?? 'false') === 'true',
    logging: (process.env.DB_LOGGING ?? 'false') === 'true',
    ssl: (process.env.DB_SSL ?? 'false') === 'true',
  },
  jwt: {
    secret: process.env.JWT_SECRET ?? 'change-me-in-production',
    accessTtl: process.env.JWT_ACCESS_TTL ?? '15m',
    refreshSecret: process.env.JWT_REFRESH_SECRET ?? 'change-me-too-in-production',
    refreshTtl: process.env.JWT_REFRESH_TTL ?? '7d',
  },
  throttle: {
    ttlMs: parseInt(process.env.THROTTLE_TTL_MS ?? '60000', 10),
    limit: parseInt(process.env.THROTTLE_LIMIT ?? '120', 10),
  },
  security: {
    bcryptRounds: parseInt(process.env.BCRYPT_ROUNDS ?? '10', 10),
  },
});

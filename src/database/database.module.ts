import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';

/**
 * Database layer.
 *
 * PostgreSQL is the production engine. The in-memory `sqljs` driver is kept
 * for local demos and the e2e suite so the entire platform can boot without
 * external services. Entities are written engine-agnostic (varchar enums,
 * simple-json documents) so both drivers share one schema definition.
 */
@Module({
  imports: [
    TypeOrmModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => {
        const db = config.get('database');
        const common = {
          autoLoadEntities: true,
          synchronize: db.synchronize,
          logging: db.logging,
        };
        if (db.type === 'sqljs') {
          return { type: 'sqljs' as const, ...common, synchronize: true };
        }
        return {
          type: 'postgres' as const,
          host: db.host,
          port: db.port,
          username: db.username,
          password: db.password,
          database: db.name,
          ssl: db.ssl ? { rejectUnauthorized: false } : false,
          ...common,
        };
      },
    }),
  ],
})
export class DatabaseModule {}

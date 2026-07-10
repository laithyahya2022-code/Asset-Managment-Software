import { ColumnType } from 'typeorm';

/**
 * Engine-portable column types. Decorators are evaluated at import time,
 * so the driver is selected from the same env var the DatabaseModule uses.
 * PostgreSQL is the default; `sqljs` is only for local demos and e2e tests.
 */
const isSqlJs = (process.env.DB_TYPE ?? 'postgres') === 'sqljs';

export const TIMESTAMP: ColumnType = isSqlJs ? 'datetime' : 'timestamp';
export const MONEY: ColumnType = 'decimal';

/** Serialise decimals as numbers instead of strings (pg returns strings). */
export const moneyTransformer = {
  to: (value?: number | null) => value,
  from: (value?: string | number | null) =>
    value === null || value === undefined ? null : Number(value),
};

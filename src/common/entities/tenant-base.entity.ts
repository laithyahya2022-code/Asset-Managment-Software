import { Column, Index } from 'typeorm';
import { BaseEntity } from './base.entity';

/**
 * Base class for every tenant-scoped row.
 *
 * Multi-tenancy model: shared database, shared schema, mandatory
 * `organizationId` discriminator column enforced at the service layer.
 * The column is indexed on every table because *every* tenant query
 * filters on it.
 */
export abstract class TenantBaseEntity extends BaseEntity {
  @Index()
  @Column({ type: 'uuid' })
  organizationId: string;
}

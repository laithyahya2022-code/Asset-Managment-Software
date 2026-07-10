import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

export enum AssetEventType {
  CREATED = 'CREATED',
  UPDATED = 'UPDATED',
  STATUS_CHANGED = 'STATUS_CHANGED',
  CHECKED_OUT = 'CHECKED_OUT',
  CHECKED_IN = 'CHECKED_IN',
  MAINTENANCE = 'MAINTENANCE',
  TRANSFERRED = 'TRANSFERRED',
  AUDITED = 'AUDITED',
  RETIRED = 'RETIRED',
  DISPOSED = 'DISPOSED',
}

/** Immutable per-asset timeline — the asset's complete history. */
@Entity('asset_events')
@Index(['organizationId', 'assetId'])
export class AssetEvent extends TenantBaseEntity {
  @Column({ type: 'uuid' })
  assetId: string;

  @Column({ type: 'varchar', length: 30 })
  type: AssetEventType;

  @Column({ length: 1000 })
  description: string;

  @Column({ type: 'uuid', nullable: true })
  actorUserId?: string | null;

  @Column({ type: 'simple-json', nullable: true })
  metadata?: Record<string, unknown> | null;
}

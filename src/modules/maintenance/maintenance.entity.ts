import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { MONEY, moneyTransformer, TIMESTAMP } from '../../common/utils/column-types';

export enum MaintenanceType {
  PREVENTIVE = 'PREVENTIVE',
  CORRECTIVE = 'CORRECTIVE',
  INSPECTION = 'INSPECTION',
  UPGRADE = 'UPGRADE',
  VENDOR_REPAIR = 'VENDOR_REPAIR',
  INTERNAL_REPAIR = 'INTERNAL_REPAIR',
}

export enum MaintenanceStatus {
  SCHEDULED = 'SCHEDULED',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED',
}

/** A maintenance / repair work order against a single asset. */
@Entity('maintenance_records')
@Index(['organizationId', 'assetId'])
@Index(['organizationId', 'status'])
@Index(['organizationId', 'scheduledFor'])
export class MaintenanceRecord extends TenantBaseEntity {
  @Column({ type: 'uuid' })
  assetId: string;

  @Column({ type: 'varchar', length: 30 })
  type: MaintenanceType;

  @Column({ type: 'varchar', length: 20, default: MaintenanceStatus.SCHEDULED })
  status: MaintenanceStatus;

  @Column({ length: 200 })
  title: string;

  @Column({ length: 2000, nullable: true })
  description?: string;

  @Column({ type: TIMESTAMP, nullable: true })
  scheduledFor?: Date | null;

  @Column({ type: TIMESTAMP, nullable: true })
  startedAt?: Date | null;

  @Column({ type: TIMESTAMP, nullable: true })
  completedAt?: Date | null;

  @Column({ type: MONEY, precision: 14, scale: 2, nullable: true, transformer: moneyTransformer })
  cost?: number | null;

  /** Vendor doing the work (for external repairs). */
  @Column({ type: 'uuid', nullable: true })
  supplierId?: string | null;

  @Column({ length: 200, nullable: true })
  performedBy?: string;

  @Column({ type: 'simple-json', nullable: true })
  partsReplaced?: Array<{ part: string; cost?: number }> | null;

  @Column({ length: 2000, nullable: true })
  resolutionNotes?: string;

  @Column({ type: 'uuid' })
  createdById: string;
}

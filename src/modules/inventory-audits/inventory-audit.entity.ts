import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { TIMESTAMP } from '../../common/utils/column-types';

export enum InventoryAuditStatus {
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED',
}

export enum ScanResult {
  MATCHED = 'MATCHED',
  WRONG_LOCATION = 'WRONG_LOCATION',
  UNKNOWN = 'UNKNOWN',
  DUPLICATE = 'DUPLICATE',
}

/**
 * A physical inventory session. Expected assets are snapshotted at start;
 * completion reconciles scans against expectations.
 */
@Entity('inventory_audits')
@Index(['organizationId', 'status'])
export class InventoryAudit extends TenantBaseEntity {
  @Column({ length: 200 })
  name: string;

  /** Scope the audit to a branch (null = whole organization). */
  @Column({ type: 'uuid', nullable: true })
  branchId?: string | null;

  @Column({ type: 'varchar', length: 20, default: InventoryAuditStatus.IN_PROGRESS })
  status: InventoryAuditStatus;

  @Column({ type: 'uuid' })
  startedById: string;

  @Column({ type: TIMESTAMP })
  startedAt: Date;

  @Column({ type: TIMESTAMP, nullable: true })
  completedAt?: Date | null;

  /** Snapshot of asset ids expected to be found in scope. */
  @Column({ type: 'simple-json' })
  expectedAssetIds: string[];

  /** Reconciliation output, filled at completion. */
  @Column({ type: 'simple-json', nullable: true })
  results?: {
    expected: number;
    scanned: number;
    matched: number;
    missingAssetIds: string[];
    wrongLocationAssetIds: string[];
    unknownCodes: string[];
  } | null;
}

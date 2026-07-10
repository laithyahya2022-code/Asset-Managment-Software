import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { TIMESTAMP } from '../../common/utils/column-types';
import { ScanResult } from './inventory-audit.entity';

/** One QR/barcode scan performed during an inventory audit. */
@Entity('inventory_audit_scans')
@Index(['organizationId', 'auditId'])
export class InventoryAuditScan extends TenantBaseEntity {
  @Column({ type: 'uuid' })
  auditId: string;

  /** Raw payload read from the QR/barcode. */
  @Column({ length: 200 })
  scannedCode: string;

  /** Resolved asset, when the code matched one. */
  @Column({ type: 'uuid', nullable: true })
  assetId?: string | null;

  @Column({ type: 'varchar', length: 20 })
  result: ScanResult;

  @Column({ type: 'uuid' })
  scannedById: string;

  @Column({ type: TIMESTAMP })
  scannedAt: Date;

  @Column({ length: 300, nullable: true })
  locationNote?: string;
}

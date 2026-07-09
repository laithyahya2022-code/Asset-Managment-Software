import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { MONEY, moneyTransformer, TIMESTAMP } from '../../common/utils/column-types';
import { AssetCondition, AssetStatus } from './asset-lifecycle';

export interface AssetAttachment {
  name: string;
  url: string;
  kind: 'image' | 'document' | 'invoice' | 'other';
  uploadedAt: string;
}

/** The central inventory record for a single physical or virtual asset. */
@Entity('assets')
@Index(['organizationId', 'assetTag'], { unique: true })
@Index(['organizationId', 'status'])
@Index(['organizationId', 'categoryId'])
@Index(['organizationId', 'branchId'])
@Index(['organizationId', 'departmentId'])
@Index(['organizationId', 'assignedEmployeeId'])
@Index(['organizationId', 'warrantyEndDate'])
export class Asset extends TenantBaseEntity {
  /** Human-scannable identifier printed on the label (also QR/barcode payload). */
  @Column({ length: 60 })
  assetTag: string;

  @Column({ length: 200 })
  name: string;

  @Index()
  @Column({ length: 120, nullable: true })
  serialNumber?: string;

  @Column({ length: 120, nullable: true })
  manufacturer?: string;

  @Column({ length: 120, nullable: true })
  model?: string;

  @Column({ type: 'uuid' })
  categoryId: string;

  @Column({ type: 'varchar', length: 30, default: AssetStatus.IN_STOCK })
  status: AssetStatus;

  @Column({ type: 'varchar', length: 20, default: AssetCondition.GOOD })
  condition: AssetCondition;

  // ── Procurement / financials ────────────────────────────────────────
  @Column({ type: TIMESTAMP, nullable: true })
  purchaseDate?: Date | null;

  @Column({ type: MONEY, precision: 14, scale: 2, nullable: true, transformer: moneyTransformer })
  purchaseCost?: number | null;

  @Column({ type: 'uuid', nullable: true })
  supplierId?: string | null;

  @Column({ length: 100, nullable: true })
  purchaseOrderNumber?: string;

  @Column({ type: 'int', nullable: true })
  usefulLifeYears?: number | null;

  @Column({ type: MONEY, precision: 14, scale: 2, nullable: true, transformer: moneyTransformer })
  salvageValue?: number | null;

  // ── Warranty ────────────────────────────────────────────────────────
  @Column({ type: TIMESTAMP, nullable: true })
  warrantyStartDate?: Date | null;

  @Column({ type: TIMESTAMP, nullable: true })
  warrantyEndDate?: Date | null;

  @Column({ length: 200, nullable: true })
  warrantyProvider?: string;

  /** Last warranty alert window raised (90/60/30/7/0), for dedup. */
  @Column({ type: 'int', nullable: true })
  lastWarrantyAlertDays?: number | null;

  // ── Placement ───────────────────────────────────────────────────────
  @Column({ type: 'uuid', nullable: true })
  assignedEmployeeId?: string | null;

  @Column({ type: 'uuid', nullable: true })
  departmentId?: string | null;

  @Column({ type: 'uuid', nullable: true })
  branchId?: string | null;

  @Column({ length: 100, nullable: true })
  building?: string;

  @Column({ length: 50, nullable: true })
  floor?: string;

  @Column({ length: 50, nullable: true })
  room?: string;

  @Column({ length: 300, nullable: true })
  locationNotes?: string;

  // ── Technical details ───────────────────────────────────────────────
  @Column({ length: 45, nullable: true })
  ipAddress?: string;

  @Column({ length: 17, nullable: true })
  macAddress?: string;

  @Column({ length: 100, nullable: true })
  operatingSystem?: string;

  @Column({ length: 100, nullable: true })
  cpu?: string;

  @Column({ length: 50, nullable: true })
  ram?: string;

  @Column({ length: 50, nullable: true })
  storage?: string;

  // ── Free-form ───────────────────────────────────────────────────────
  @Column({ length: 2000, nullable: true })
  notes?: string;

  /** Values for the category's custom field definitions. */
  @Column({ type: 'simple-json', nullable: true })
  customFields?: Record<string, unknown> | null;

  /** Metadata for externally stored files (images, invoices, documents). */
  @Column({ type: 'simple-json', nullable: true })
  attachments?: AssetAttachment[] | null;

  @Column({ type: TIMESTAMP, nullable: true })
  retiredAt?: Date | null;

  @Column({ type: TIMESTAMP, nullable: true })
  disposedAt?: Date | null;
}

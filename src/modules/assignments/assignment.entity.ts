import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { TIMESTAMP } from '../../common/utils/column-types';
import { AssetCondition } from '../assets/asset-lifecycle';

export enum AssignmentStatus {
  ACTIVE = 'ACTIVE',
  RETURNED = 'RETURNED',
}

/**
 * One check-out → check-in cycle of an asset to an employee, including
 * digital signatures, condition/damage records and photo references.
 */
@Entity('asset_assignments')
@Index(['organizationId', 'assetId'])
@Index(['organizationId', 'employeeId'])
@Index(['organizationId', 'status'])
export class AssetAssignment extends TenantBaseEntity {
  @Column({ type: 'uuid' })
  assetId: string;

  @Column({ type: 'uuid' })
  employeeId: string;

  @Column({ type: 'varchar', length: 20, default: AssignmentStatus.ACTIVE })
  status: AssignmentStatus;

  // ── Check-out ───────────────────────────────────────────────────────
  @Column({ type: 'uuid' })
  checkedOutById: string;

  @Column({ type: TIMESTAMP })
  checkedOutAt: Date;

  @Column({ type: TIMESTAMP, nullable: true })
  expectedReturnAt?: Date | null;

  @Column({ type: 'varchar', length: 20 })
  checkoutCondition: AssetCondition;

  /** Base64 data-URL of the employee's signature at hand-over. */
  @Column({ type: 'text', nullable: true })
  checkoutSignature?: string | null;

  @Column({ length: 1000, nullable: true })
  checkoutNotes?: string;

  // ── Check-in ────────────────────────────────────────────────────────
  @Column({ type: 'uuid', nullable: true })
  checkedInById?: string | null;

  @Column({ type: TIMESTAMP, nullable: true })
  returnedAt?: Date | null;

  @Column({ type: 'varchar', length: 20, nullable: true })
  checkinCondition?: AssetCondition | null;

  @Column({ type: 'text', nullable: true })
  checkinSignature?: string | null;

  @Column({ length: 1000, nullable: true })
  damageNotes?: string;

  /** URLs of photos taken at hand-over / return (object storage). */
  @Column({ type: 'simple-json', nullable: true })
  photos?: string[] | null;

  /** Set once an overdue alert has been raised, to avoid duplicates. */
  @Column({ default: false })
  overdueNotified: boolean;
}

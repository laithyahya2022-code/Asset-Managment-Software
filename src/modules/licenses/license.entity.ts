import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { MONEY, moneyTransformer, TIMESTAMP } from '../../common/utils/column-types';

export enum LicenseType {
  PERPETUAL = 'PERPETUAL',
  SUBSCRIPTION = 'SUBSCRIPTION',
  TRIAL = 'TRIAL',
  OEM = 'OEM',
  VOLUME = 'VOLUME',
}

/** A software license contract with a seat pool. */
@Entity('software_licenses')
@Index(['organizationId', 'name'])
@Index(['organizationId', 'expiryDate'])
export class SoftwareLicense extends TenantBaseEntity {
  @Column({ length: 200 })
  name: string;

  @Column({ length: 200, nullable: true })
  vendor?: string;

  /** Stored as-is; excluded from list serialisation at the controller. */
  @Column({ length: 500, nullable: true })
  licenseKey?: string;

  @Column({ type: 'varchar', length: 20, default: LicenseType.SUBSCRIPTION })
  type: LicenseType;

  @Column({ type: 'int', default: 1 })
  seats: number;

  @Column({ type: TIMESTAMP, nullable: true })
  purchaseDate?: Date | null;

  @Column({ type: MONEY, precision: 14, scale: 2, nullable: true, transformer: moneyTransformer })
  purchaseCost?: number | null;

  @Column({ type: 'uuid', nullable: true })
  supplierId?: string | null;

  @Column({ type: TIMESTAMP, nullable: true })
  expiryDate?: Date | null;

  @Column({ type: TIMESTAMP, nullable: true })
  renewalDate?: Date | null;

  @Column({ length: 2000, nullable: true })
  notes?: string;

  /** Set once an expiry alert has been raised for the current window. */
  @Column({ type: 'int', nullable: true })
  lastExpiryAlertDays?: number | null;
}

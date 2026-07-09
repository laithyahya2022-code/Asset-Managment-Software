import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { TIMESTAMP } from '../../common/utils/column-types';

/** Consumption of one seat by a device and/or a user. */
@Entity('license_assignments')
@Index(['organizationId', 'licenseId'])
export class LicenseAssignment extends TenantBaseEntity {
  @Column({ type: 'uuid' })
  licenseId: string;

  @Column({ type: 'uuid', nullable: true })
  assetId?: string | null;

  @Column({ type: 'uuid', nullable: true })
  employeeId?: string | null;

  @Column({ type: 'uuid' })
  assignedById: string;

  @Column({ type: TIMESTAMP })
  assignedAt: Date;

  @Column({ type: TIMESTAMP, nullable: true })
  releasedAt?: Date | null;
}

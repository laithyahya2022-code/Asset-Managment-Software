import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

/** An organizational unit, optionally anchored to a branch. */
@Entity('departments')
@Index(['organizationId', 'code'], { unique: true })
export class Department extends TenantBaseEntity {
  @Column({ length: 200 })
  name: string;

  @Column({ length: 30 })
  code: string;

  @Column({ type: 'uuid', nullable: true })
  branchId?: string | null;

  @Column({ length: 500, nullable: true })
  description?: string;

  @Column({ type: 'uuid', nullable: true })
  managerEmployeeId?: string | null;

  @Column({ default: true })
  isActive: boolean;
}

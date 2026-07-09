import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

/**
 * A person who can hold assets. Distinct from User: most employees never
 * sign in, and IT staff may manage assets for people without accounts.
 */
@Entity('employees')
@Index(['organizationId', 'employeeNumber'], { unique: true })
export class Employee extends TenantBaseEntity {
  @Column({ length: 50 })
  employeeNumber: string;

  @Column({ length: 200 })
  fullName: string;

  @Index()
  @Column({ length: 320, nullable: true })
  email?: string;

  @Column({ length: 50, nullable: true })
  phone?: string;

  @Column({ length: 200, nullable: true })
  jobTitle?: string;

  @Column({ type: 'uuid', nullable: true })
  departmentId?: string | null;

  @Column({ type: 'uuid', nullable: true })
  branchId?: string | null;

  /** Optional link to a login account for self-service. */
  @Column({ type: 'uuid', nullable: true })
  userId?: string | null;

  @Column({ default: true })
  isActive: boolean;
}

import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

/** A physical site of the organization (office, campus, plant…). */
@Entity('branches')
@Index(['organizationId', 'code'], { unique: true })
export class Branch extends TenantBaseEntity {
  @Column({ length: 200 })
  name: string;

  @Column({ length: 30 })
  code: string;

  @Column({ length: 300, nullable: true })
  address?: string;

  @Column({ length: 100, nullable: true })
  city?: string;

  @Column({ length: 100, nullable: true })
  country?: string;

  @Column({ length: 50, nullable: true })
  timezone?: string;

  @Column({ default: true })
  isActive: boolean;
}

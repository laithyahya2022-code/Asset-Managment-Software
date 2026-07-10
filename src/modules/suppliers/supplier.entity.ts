import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

/** A vendor from whom assets, licenses or services are purchased. */
@Entity('suppliers')
@Index(['organizationId', 'name'])
export class Supplier extends TenantBaseEntity {
  @Column({ length: 200 })
  name: string;

  @Column({ length: 200, nullable: true })
  contactName?: string;

  @Column({ length: 320, nullable: true })
  email?: string;

  @Column({ length: 50, nullable: true })
  phone?: string;

  @Column({ length: 300, nullable: true })
  website?: string;

  @Column({ length: 300, nullable: true })
  address?: string;

  @Column({ length: 1000, nullable: true })
  notes?: string;

  @Column({ default: true })
  isActive: boolean;
}

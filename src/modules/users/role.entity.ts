import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

/**
 * A named permission set. System roles are seeded per tenant and locked;
 * tenants may create additional custom roles.
 */
@Entity('roles')
@Index(['organizationId', 'name'], { unique: true })
export class Role extends TenantBaseEntity {
  @Column({ length: 100 })
  name: string;

  @Column({ length: 500, nullable: true })
  description?: string;

  @Column({ type: 'simple-json' })
  permissions: string[];

  @Column({ default: false })
  isSystem: boolean;
}

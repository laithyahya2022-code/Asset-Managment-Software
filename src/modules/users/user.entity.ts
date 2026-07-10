import { Exclude } from 'class-transformer';
import { Column, Entity, Index, JoinColumn, ManyToOne } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { TIMESTAMP } from '../../common/utils/column-types';
import { Role } from './role.entity';

/** An account that can sign in. Linked 1-1 to an Employee where relevant. */
@Entity('users')
@Index(['organizationId', 'email'], { unique: true })
export class User extends TenantBaseEntity {
  @Column({ length: 320 })
  email: string;

  @Exclude()
  @Column({ length: 100 })
  passwordHash: string;

  @Column({ length: 200 })
  fullName: string;

  @Column({ type: 'uuid' })
  roleId: string;

  @ManyToOne(() => Role, { eager: true })
  @JoinColumn({ name: 'roleId' })
  role: Role;

  @Column({ default: true })
  isActive: boolean;

  @Column({ type: TIMESTAMP, nullable: true })
  lastLoginAt?: Date | null;

  /** Hash of the currently valid refresh token (rotation on every refresh). */
  @Exclude()
  @Column({ type: 'varchar', length: 100, nullable: true })
  refreshTokenHash?: string | null;
}

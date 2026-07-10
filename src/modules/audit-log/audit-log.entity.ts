import { Column, Entity, Index } from 'typeorm';
import { BaseEntity } from '../../common/entities/base.entity';

/**
 * Append-only trail of every state-changing action in the platform.
 * Never updated, never deleted.
 */
@Entity('audit_logs')
export class AuditLog extends BaseEntity {
  @Index()
  @Column({ type: 'uuid', nullable: true })
  organizationId?: string | null;

  @Index()
  @Column({ type: 'uuid', nullable: true })
  actorUserId?: string | null;

  @Column({ type: 'varchar', length: 320, nullable: true })
  actorEmail?: string | null;

  /** e.g. `asset.created`, `auth.login`, `role.updated` */
  @Index()
  @Column({ length: 150 })
  action: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  entityType?: string | null;

  @Index()
  @Column({ type: 'varchar', length: 64, nullable: true })
  entityId?: string | null;

  @Column({ type: 'int', nullable: true })
  statusCode?: number | null;

  @Column({ type: 'varchar', length: 64, nullable: true })
  ipAddress?: string | null;

  @Column({ type: 'simple-json', nullable: true })
  metadata?: Record<string, unknown> | null;
}

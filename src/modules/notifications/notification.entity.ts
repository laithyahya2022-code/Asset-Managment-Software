import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';
import { TIMESTAMP } from '../../common/utils/column-types';

export enum NotificationType {
  WARRANTY_EXPIRING = 'WARRANTY_EXPIRING',
  WARRANTY_EXPIRED = 'WARRANTY_EXPIRED',
  LICENSE_EXPIRING = 'LICENSE_EXPIRING',
  LICENSE_EXPIRED = 'LICENSE_EXPIRED',
  RETURN_OVERDUE = 'RETURN_OVERDUE',
  MAINTENANCE_DUE = 'MAINTENANCE_DUE',
  ASSET_ASSIGNED = 'ASSET_ASSIGNED',
  ASSET_RETURNED = 'ASSET_RETURNED',
  SYSTEM = 'SYSTEM',
}

/** An in-app notification addressed to a single user. */
@Entity('notifications')
@Index(['organizationId', 'userId', 'isRead'])
export class Notification extends TenantBaseEntity {
  @Column({ type: 'uuid' })
  userId: string;

  @Column({ type: 'varchar', length: 30 })
  type: NotificationType;

  @Column({ length: 200 })
  title: string;

  @Column({ length: 1000 })
  message: string;

  @Column({ default: false })
  isRead: boolean;

  @Column({ type: TIMESTAMP, nullable: true })
  readAt?: Date | null;

  @Column({ type: 'simple-json', nullable: true })
  metadata?: Record<string, unknown> | null;
}

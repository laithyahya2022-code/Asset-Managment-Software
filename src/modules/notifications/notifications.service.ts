import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { buildPage, Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { User } from '../users/user.entity';
import { Notification, NotificationType } from './notification.entity';

/**
 * Notification hub. In-app delivery is implemented; the `dispatch` seam is
 * where additional channels (SMTP email, Slack, Teams, push) plug in.
 */
@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  constructor(
    @InjectRepository(Notification)
    private readonly notifications: Repository<Notification>,
    @InjectRepository(User) private readonly users: Repository<User>,
  ) {}

  async notifyUser(
    organizationId: string,
    userId: string,
    type: NotificationType,
    title: string,
    message: string,
    metadata?: Record<string, unknown>,
  ): Promise<Notification> {
    const notification = await this.notifications.save(
      this.notifications.create({ organizationId, userId, type, title, message, metadata }),
    );
    this.dispatch(notification);
    return notification;
  }

  /** Notify every user in the tenant holding a given permission. */
  async notifyByPermission(
    organizationId: string,
    permission: string,
    type: NotificationType,
    title: string,
    message: string,
    metadata?: Record<string, unknown>,
  ): Promise<number> {
    const users = await this.users.find({ where: { organizationId, isActive: true } });
    const recipients = users.filter((u) => u.role?.permissions?.includes(permission));
    for (const user of recipients) {
      await this.notifyUser(organizationId, user.id, type, title, message, metadata);
    }
    return recipients.length;
  }

  async listForUser(
    organizationId: string,
    userId: string,
    query: PageQueryDto,
    unreadOnly = false,
  ): Promise<Page<Notification>> {
    const where = unreadOnly
      ? { organizationId, userId, isRead: false }
      : { organizationId, userId };
    const [items, total] = await this.notifications.findAndCount({
      where,
      order: { createdAt: 'DESC' },
      skip: (query.page - 1) * query.pageSize,
      take: query.pageSize,
    });
    return buildPage(items, total, query);
  }

  async markRead(organizationId: string, userId: string, id: string): Promise<Notification> {
    const notification = await this.notifications.findOne({
      where: { id, organizationId, userId },
    });
    if (!notification) throw new NotFoundException('Notification not found');
    notification.isRead = true;
    notification.readAt = new Date();
    return this.notifications.save(notification);
  }

  async markAllRead(organizationId: string, userId: string): Promise<void> {
    await this.notifications.update(
      { organizationId, userId, isRead: false },
      { isRead: true, readAt: new Date() },
    );
  }

  async unreadCount(organizationId: string, userId: string): Promise<{ unread: number }> {
    const unread = await this.notifications.count({
      where: { organizationId, userId, isRead: false },
    });
    return { unread };
  }

  /**
   * Channel fan-out seam. Wire SMTP / chat integrations here; kept
   * non-blocking so channel outages never affect the write path.
   */
  private dispatch(notification: Notification): void {
    this.logger.debug(
      `notification ${notification.type} → user ${notification.userId}: ${notification.title}`,
    );
  }
}

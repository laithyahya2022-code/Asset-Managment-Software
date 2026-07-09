import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { InjectRepository } from '@nestjs/typeorm';
import { LessThanOrEqual, Repository } from 'typeorm';
import { PERMISSIONS } from '../../common/security/permissions';
import { Asset } from '../assets/asset.entity';
import { AssignmentsService } from '../assignments/assignments.service';
import { SoftwareLicense } from '../licenses/license.entity';
import { Organization } from '../organizations/organization.entity';
import { NotificationType } from './notification.entity';
import { NotificationsService } from './notifications.service';

const DEFAULT_WINDOWS = [90, 60, 30, 7];

/**
 * Background alerting jobs. Each run is idempotent: the entity remembers
 * the last alert window raised, so a window fires exactly once.
 */
@Injectable()
export class AlertsScheduler {
  private readonly logger = new Logger(AlertsScheduler.name);

  constructor(
    @InjectRepository(Asset) private readonly assets: Repository<Asset>,
    @InjectRepository(SoftwareLicense)
    private readonly licenses: Repository<SoftwareLicense>,
    @InjectRepository(Organization)
    private readonly organizations: Repository<Organization>,
    private readonly notificationsService: NotificationsService,
    private readonly assignmentsService: AssignmentsService,
  ) {}

  @Cron(CronExpression.EVERY_DAY_AT_7AM)
  async warrantyAlerts(): Promise<void> {
    const now = Date.now();
    const orgs = await this.organizations.find({ where: { isActive: true } });

    for (const org of orgs) {
      const windows = org.settings?.warrantyAlertDays ?? DEFAULT_WINDOWS;
      const horizon = new Date(now + Math.max(...windows) * 86_400_000);
      const candidates = await this.assets.find({
        where: {
          organizationId: org.id,
          // SQL comparison is false for NULL, so this excludes missing dates.
          warrantyEndDate: LessThanOrEqual(horizon),
        },
      });

      for (const asset of candidates) {
        if (!asset.warrantyEndDate) continue;
        const daysLeft = Math.ceil(
          (new Date(asset.warrantyEndDate).getTime() - now) / 86_400_000,
        );
        const window = daysLeft < 0 ? 0 : [...windows].sort((a, b) => a - b).find((w) => daysLeft <= w);
        if (window === undefined) continue;
        if (asset.lastWarrantyAlertDays !== null && asset.lastWarrantyAlertDays !== undefined && asset.lastWarrantyAlertDays <= window) {
          continue; // this or a tighter window already fired
        }

        await this.notificationsService.notifyByPermission(
          org.id,
          PERMISSIONS.ASSETS[0],
          daysLeft < 0 ? NotificationType.WARRANTY_EXPIRED : NotificationType.WARRANTY_EXPIRING,
          daysLeft < 0
            ? `Warranty expired: ${asset.assetTag}`
            : `Warranty expiring in ${daysLeft} day(s): ${asset.assetTag}`,
          `${asset.name} (${asset.assetTag}) — warranty ends ${new Date(asset.warrantyEndDate).toISOString().slice(0, 10)}`,
          { assetId: asset.id, daysLeft },
        );
        asset.lastWarrantyAlertDays = window;
        await this.assets.save(asset);
      }
    }
    this.logger.log('Warranty alert sweep complete');
  }

  @Cron(CronExpression.EVERY_DAY_AT_7AM)
  async licenseAlerts(): Promise<void> {
    const now = Date.now();
    const orgs = await this.organizations.find({ where: { isActive: true } });

    for (const org of orgs) {
      const windows = org.settings?.licenseAlertDays ?? DEFAULT_WINDOWS;
      const horizon = new Date(now + Math.max(...windows) * 86_400_000);
      const candidates = await this.licenses.find({
        where: {
          organizationId: org.id,
          expiryDate: LessThanOrEqual(horizon),
        },
      });

      for (const license of candidates) {
        if (!license.expiryDate) continue;
        const daysLeft = Math.ceil((new Date(license.expiryDate).getTime() - now) / 86_400_000);
        const window = daysLeft < 0 ? 0 : [...windows].sort((a, b) => a - b).find((w) => daysLeft <= w);
        if (window === undefined) continue;
        if (license.lastExpiryAlertDays !== null && license.lastExpiryAlertDays !== undefined && license.lastExpiryAlertDays <= window) {
          continue;
        }

        await this.notificationsService.notifyByPermission(
          org.id,
          PERMISSIONS.LICENSES[0],
          daysLeft < 0 ? NotificationType.LICENSE_EXPIRED : NotificationType.LICENSE_EXPIRING,
          daysLeft < 0
            ? `License expired: ${license.name}`
            : `License expiring in ${daysLeft} day(s): ${license.name}`,
          `${license.name}${license.vendor ? ` (${license.vendor})` : ''} — expires ${new Date(license.expiryDate).toISOString().slice(0, 10)}`,
          { licenseId: license.id, daysLeft },
        );
        license.lastExpiryAlertDays = window;
        await this.licenses.save(license);
      }
    }
    this.logger.log('License alert sweep complete');
  }

  @Cron(CronExpression.EVERY_HOUR)
  async overdueReturns(): Promise<void> {
    const overdue = await this.assignmentsService.findOverdue();
    const fresh = overdue.filter((a) => !a.overdueNotified);
    for (const assignment of fresh) {
      await this.notificationsService.notifyByPermission(
        assignment.organizationId,
        PERMISSIONS.ASSIGNMENTS_CHECKIN,
        NotificationType.RETURN_OVERDUE,
        'Asset return overdue',
        `Assignment ${assignment.id} was due back ${assignment.expectedReturnAt?.toISOString().slice(0, 10)}`,
        { assignmentId: assignment.id, assetId: assignment.assetId },
      );
    }
    await this.assignmentsService.markOverdueNotified(fresh.map((a) => a.id));
    if (fresh.length > 0) this.logger.log(`Raised ${fresh.length} overdue-return alert(s)`);
  }
}

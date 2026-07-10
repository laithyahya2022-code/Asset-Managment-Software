import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Asset } from '../assets/asset.entity';
import { AssignmentsModule } from '../assignments/assignments.module';
import { SoftwareLicense } from '../licenses/license.entity';
import { Organization } from '../organizations/organization.entity';
import { User } from '../users/user.entity';
import { AlertsScheduler } from './alerts.scheduler';
import { Notification } from './notification.entity';
import { NotificationsController } from './notifications.controller';
import { NotificationsService } from './notifications.service';

@Module({
  imports: [
    TypeOrmModule.forFeature([Notification, User, Asset, SoftwareLicense, Organization]),
    AssignmentsModule,
  ],
  controllers: [NotificationsController],
  providers: [NotificationsService, AlertsScheduler],
  exports: [NotificationsService],
})
export class NotificationsModule {}

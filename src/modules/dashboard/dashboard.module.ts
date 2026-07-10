import { Controller, Get, Module } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { TypeOrmModule } from '@nestjs/typeorm';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { AssetEvent } from '../assets/asset-event.entity';
import { Asset } from '../assets/asset.entity';
import { AssetsModule } from '../assets/assets.module';
import { AssetAssignment } from '../assignments/assignment.entity';
import { SoftwareLicense } from '../licenses/license.entity';
import { MaintenanceRecord } from '../maintenance/maintenance.entity';
import { DashboardService } from './dashboard.service';

@ApiTags('Dashboard')
@ApiBearerAuth()
@Controller('dashboard')
export class DashboardController {
  constructor(private readonly service: DashboardService) {}

  @Get()
  @RequirePermissions(PERMISSIONS.DASHBOARD_READ)
  @ApiOperation({ summary: 'Executive dashboard: totals, breakdowns, financials, activity' })
  summary(@CurrentUser() user: AuthenticatedUser) {
    return this.service.summary(user.organizationId);
  }
}

@Module({
  imports: [
    TypeOrmModule.forFeature([
      Asset,
      AssetAssignment,
      SoftwareLicense,
      MaintenanceRecord,
      AssetEvent,
    ]),
    AssetsModule,
  ],
  controllers: [DashboardController],
  providers: [DashboardService],
})
export class DashboardModule {}

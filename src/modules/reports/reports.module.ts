import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Asset } from '../assets/asset.entity';
import { AssetsModule } from '../assets/assets.module';
import { AssetAssignment } from '../assignments/assignment.entity';
import { SoftwareLicense } from '../licenses/license.entity';
import { MaintenanceRecord } from '../maintenance/maintenance.entity';
import { ExportService } from './export.service';
import { ReportsController } from './reports.controller';
import { ReportsService } from './reports.service';

@Module({
  imports: [
    TypeOrmModule.forFeature([Asset, AssetAssignment, SoftwareLicense, MaintenanceRecord]),
    AssetsModule,
  ],
  controllers: [ReportsController],
  providers: [ReportsService, ExportService],
})
export class ReportsModule {}

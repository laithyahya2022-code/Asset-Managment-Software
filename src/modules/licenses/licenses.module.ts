import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Asset } from '../assets/asset.entity';
import { Employee } from '../employees/employee.entity';
import { LicenseAssignment } from './license-assignment.entity';
import { SoftwareLicense } from './license.entity';
import { LicensesController } from './licenses.controller';
import { LicensesService } from './licenses.service';

@Module({
  imports: [TypeOrmModule.forFeature([SoftwareLicense, LicenseAssignment, Asset, Employee])],
  controllers: [LicensesController],
  providers: [LicensesService],
  exports: [LicensesService],
})
export class LicensesModule {}

import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AssetEvent } from '../assets/asset-event.entity';
import { Asset } from '../assets/asset.entity';
import { Employee } from '../employees/employee.entity';
import { AssetAssignment } from './assignment.entity';
import { AssignmentsController } from './assignments.controller';
import { AssignmentsService } from './assignments.service';

@Module({
  imports: [TypeOrmModule.forFeature([AssetAssignment, Asset, Employee, AssetEvent])],
  controllers: [AssignmentsController],
  providers: [AssignmentsService],
  exports: [AssignmentsService],
})
export class AssignmentsModule {}

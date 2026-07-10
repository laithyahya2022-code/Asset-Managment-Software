import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AssetCategory } from '../categories/asset-category.entity';
import { Organization } from '../organizations/organization.entity';
import { AssetEvent } from './asset-event.entity';
import { Asset } from './asset.entity';
import { AssetsController } from './assets.controller';
import { AssetsService } from './assets.service';
import { LabelsService } from './labels.service';

@Module({
  imports: [TypeOrmModule.forFeature([Asset, AssetEvent, AssetCategory, Organization])],
  controllers: [AssetsController],
  providers: [AssetsService, LabelsService],
  exports: [AssetsService, LabelsService],
})
export class AssetsModule {}

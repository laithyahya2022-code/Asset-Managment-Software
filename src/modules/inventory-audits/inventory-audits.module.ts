import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Asset } from '../assets/asset.entity';
import { AssetsModule } from '../assets/assets.module';
import { InventoryAuditScan } from './inventory-audit-scan.entity';
import { InventoryAudit } from './inventory-audit.entity';
import { InventoryAuditsController } from './inventory-audits.controller';
import { InventoryAuditsService } from './inventory-audits.service';

@Module({
  imports: [
    TypeOrmModule.forFeature([InventoryAudit, InventoryAuditScan, Asset]),
    AssetsModule,
  ],
  controllers: [InventoryAuditsController],
  providers: [InventoryAuditsService],
  exports: [InventoryAuditsService],
})
export class InventoryAuditsModule {}

import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Between, IsNull, LessThan, Repository } from 'typeorm';
import { AssetEvent } from '../assets/asset-event.entity';
import { AssetStatus } from '../assets/asset-lifecycle';
import { Asset } from '../assets/asset.entity';
import { AssetsService } from '../assets/assets.service';
import { AssetAssignment, AssignmentStatus } from '../assignments/assignment.entity';
import { SoftwareLicense } from '../licenses/license.entity';
import {
  MaintenanceRecord,
  MaintenanceStatus,
} from '../maintenance/maintenance.entity';

/**
 * Executive dashboard aggregations. Grouped counts are computed in SQL;
 * only financial roll-ups load rows (cost columns) into memory.
 */
@Injectable()
export class DashboardService {
  constructor(
    @InjectRepository(Asset) private readonly assets: Repository<Asset>,
    @InjectRepository(AssetAssignment)
    private readonly assignments: Repository<AssetAssignment>,
    @InjectRepository(SoftwareLicense)
    private readonly licenses: Repository<SoftwareLicense>,
    @InjectRepository(MaintenanceRecord)
    private readonly maintenance: Repository<MaintenanceRecord>,
    @InjectRepository(AssetEvent) private readonly events: Repository<AssetEvent>,
    private readonly assetsService: AssetsService,
  ) {}

  async summary(organizationId: string) {
    const in90Days = new Date(Date.now() + 90 * 86_400_000);
    const now = new Date();

    const [
      totalAssets,
      assignedAssets,
      availableAssets,
      maintenanceAssets,
      retiredAssets,
      warrantyExpiring90d,
      licenseExpiring90d,
      overdueReturns,
      openMaintenance,
      byStatus,
      byCategory,
      byBranch,
      byDepartment,
      financials,
      recentEvents,
    ] = await Promise.all([
      this.assets.count({ where: { organizationId } }),
      this.assets.count({ where: { organizationId, status: AssetStatus.ASSIGNED } }),
      this.assets.count({ where: { organizationId, status: AssetStatus.IN_STOCK } }),
      this.assets.count({
        where: [
          { organizationId, status: AssetStatus.IN_MAINTENANCE },
          { organizationId, status: AssetStatus.IN_REPAIR },
        ],
      }),
      this.assets.count({ where: { organizationId, status: AssetStatus.RETIRED } }),
      this.assets.count({
        where: { organizationId, warrantyEndDate: Between(now, in90Days) },
      }),
      this.licenses.count({
        where: { organizationId, expiryDate: Between(now, in90Days) },
      }),
      this.assignments.count({
        where: {
          organizationId,
          status: AssignmentStatus.ACTIVE,
          expectedReturnAt: LessThan(now),
          returnedAt: IsNull(),
        },
      }),
      this.maintenance.count({
        where: [
          { organizationId, status: MaintenanceStatus.SCHEDULED },
          { organizationId, status: MaintenanceStatus.IN_PROGRESS },
        ],
      }),
      this.groupCount('status', organizationId),
      this.groupCount('categoryId', organizationId),
      this.groupCount('branchId', organizationId),
      this.groupCount('departmentId', organizationId),
      this.financials(organizationId),
      this.events.find({
        where: { organizationId },
        order: { createdAt: 'DESC' },
        take: 15,
      }),
    ]);

    return {
      totals: {
        totalAssets,
        assignedAssets,
        availableAssets,
        maintenanceAssets,
        retiredAssets,
        warrantyExpiring90d,
        licenseExpiring90d,
        overdueReturns,
        openMaintenance,
      },
      breakdowns: { byStatus, byCategory, byBranch, byDepartment },
      financials,
      recentActivity: recentEvents,
    };
  }

  private async groupCount(column: keyof Asset & string, organizationId: string) {
    const rows = await this.assets
      .createQueryBuilder('asset')
      .select(`asset.${column}`, 'key')
      .addSelect('COUNT(*)', 'count')
      .where('asset.organizationId = :organizationId', { organizationId })
      .groupBy(`asset.${column}`)
      .getRawMany();
    return rows.map((r) => ({ key: r.key ?? 'unspecified', count: Number(r.count) }));
  }

  private async financials(organizationId: string) {
    const assets = await this.assets.find({
      where: { organizationId },
      select: ['id', 'purchaseCost', 'purchaseDate', 'usefulLifeYears', 'salvageValue'],
    });
    let totalPurchaseCost = 0;
    let currentBookValue = 0;
    for (const asset of assets) {
      if (asset.purchaseCost != null) totalPurchaseCost += Number(asset.purchaseCost);
      const dep = this.assetsService.depreciation(asset as Asset);
      if (dep) currentBookValue += dep.currentBookValue;
      else if (asset.purchaseCost != null) currentBookValue += Number(asset.purchaseCost);
    }
    const { sum: maintenanceSpend } = await this.maintenance
      .createQueryBuilder('m')
      .select('COALESCE(SUM(m.cost), 0)', 'sum')
      .where('m.organizationId = :organizationId', { organizationId })
      .andWhere('m.status = :status', { status: MaintenanceStatus.COMPLETED })
      .getRawOne();

    return {
      totalPurchaseCost: Number(totalPurchaseCost.toFixed(2)),
      currentBookValue: Number(currentBookValue.toFixed(2)),
      accumulatedDepreciation: Number((totalPurchaseCost - currentBookValue).toFixed(2)),
      maintenanceSpend: Number(maintenanceSpend ?? 0),
    };
  }
}

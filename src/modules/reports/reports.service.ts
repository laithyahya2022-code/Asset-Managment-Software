import { BadRequestException, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Between, IsNull, LessThan, Repository } from 'typeorm';
import { AssetsService } from '../assets/assets.service';
import { Asset } from '../assets/asset.entity';
import { AssetAssignment, AssignmentStatus } from '../assignments/assignment.entity';
import { SoftwareLicense } from '../licenses/license.entity';
import { MaintenanceRecord } from '../maintenance/maintenance.entity';
import { TabularReport } from './export.service';

export const REPORT_TYPES = [
  'asset-inventory',
  'warranty',
  'maintenance',
  'assignments',
  'licenses',
  'financial',
] as const;
export type ReportType = (typeof REPORT_TYPES)[number];

const MAX_REPORT_ROWS = 50_000;

/** Builds the tabular datasets behind every report type. */
@Injectable()
export class ReportsService {
  constructor(
    @InjectRepository(Asset) private readonly assets: Repository<Asset>,
    @InjectRepository(AssetAssignment)
    private readonly assignments: Repository<AssetAssignment>,
    @InjectRepository(SoftwareLicense)
    private readonly licenses: Repository<SoftwareLicense>,
    @InjectRepository(MaintenanceRecord)
    private readonly maintenance: Repository<MaintenanceRecord>,
    private readonly assetsService: AssetsService,
  ) {}

  async build(organizationId: string, type: ReportType): Promise<TabularReport> {
    switch (type) {
      case 'asset-inventory':
        return this.assetInventory(organizationId);
      case 'warranty':
        return this.warranty(organizationId);
      case 'maintenance':
        return this.maintenanceReport(organizationId);
      case 'assignments':
        return this.assignmentsReport(organizationId);
      case 'licenses':
        return this.licensesReport(organizationId);
      case 'financial':
        return this.financial(organizationId);
      default:
        throw new BadRequestException(
          `Unknown report type. Available: ${REPORT_TYPES.join(', ')}`,
        );
    }
  }

  private async assetInventory(organizationId: string): Promise<TabularReport> {
    const rows = await this.assets.find({
      where: { organizationId },
      order: { assetTag: 'ASC' },
      take: MAX_REPORT_ROWS,
    });
    return {
      title: 'Asset Inventory Report',
      generatedAt: new Date(),
      columns: [
        { key: 'assetTag', header: 'Asset Tag' },
        { key: 'name', header: 'Name', width: 30 },
        { key: 'serialNumber', header: 'Serial Number' },
        { key: 'manufacturer', header: 'Manufacturer' },
        { key: 'model', header: 'Model' },
        { key: 'status', header: 'Status' },
        { key: 'condition', header: 'Condition' },
        { key: 'purchaseDate', header: 'Purchase Date' },
        { key: 'purchaseCost', header: 'Purchase Cost' },
        { key: 'warrantyEndDate', header: 'Warranty End' },
      ],
      rows: rows as unknown as Array<Record<string, unknown>>,
    };
  }

  private async warranty(organizationId: string): Promise<TabularReport> {
    const in180Days = new Date(Date.now() + 180 * 86_400_000);
    const rows = await this.assets.find({
      where: { organizationId, warrantyEndDate: LessThan(in180Days) },
      order: { warrantyEndDate: 'ASC' },
      take: MAX_REPORT_ROWS,
    });
    return {
      title: 'Warranty Report (expired + next 180 days)',
      generatedAt: new Date(),
      columns: [
        { key: 'assetTag', header: 'Asset Tag' },
        { key: 'name', header: 'Name', width: 30 },
        { key: 'warrantyStartDate', header: 'Warranty Start' },
        { key: 'warrantyEndDate', header: 'Warranty End' },
        { key: 'warrantyProvider', header: 'Provider' },
        { key: 'daysLeft', header: 'Days Left' },
      ],
      rows: rows.map((a) => ({
        ...a,
        daysLeft: a.warrantyEndDate
          ? Math.ceil((new Date(a.warrantyEndDate).getTime() - Date.now()) / 86_400_000)
          : null,
      })),
    };
  }

  private async maintenanceReport(organizationId: string): Promise<TabularReport> {
    const rows = await this.maintenance.find({
      where: { organizationId },
      order: { createdAt: 'DESC' },
      take: MAX_REPORT_ROWS,
    });
    return {
      title: 'Maintenance Report',
      generatedAt: new Date(),
      columns: [
        { key: 'title', header: 'Title', width: 30 },
        { key: 'assetId', header: 'Asset ID', width: 38 },
        { key: 'type', header: 'Type' },
        { key: 'status', header: 'Status' },
        { key: 'scheduledFor', header: 'Scheduled' },
        { key: 'completedAt', header: 'Completed' },
        { key: 'cost', header: 'Cost' },
        { key: 'performedBy', header: 'Performed By' },
      ],
      rows: rows as unknown as Array<Record<string, unknown>>,
    };
  }

  private async assignmentsReport(organizationId: string): Promise<TabularReport> {
    const rows = await this.assignments.find({
      where: { organizationId },
      order: { checkedOutAt: 'DESC' },
      take: MAX_REPORT_ROWS,
    });
    const now = Date.now();
    return {
      title: 'Employee Asset Assignment Report',
      generatedAt: new Date(),
      columns: [
        { key: 'assetId', header: 'Asset ID', width: 38 },
        { key: 'employeeId', header: 'Employee ID', width: 38 },
        { key: 'status', header: 'Status' },
        { key: 'checkedOutAt', header: 'Checked Out' },
        { key: 'expectedReturnAt', header: 'Expected Return' },
        { key: 'returnedAt', header: 'Returned' },
        { key: 'overdue', header: 'Overdue' },
      ],
      rows: rows.map((a) => ({
        ...a,
        overdue:
          a.status === AssignmentStatus.ACTIVE &&
          a.expectedReturnAt &&
          new Date(a.expectedReturnAt).getTime() < now
            ? 'YES'
            : '',
      })),
    };
  }

  private async licensesReport(organizationId: string): Promise<TabularReport> {
    const rows = await this.licenses.find({
      where: { organizationId },
      order: { expiryDate: 'ASC' },
      take: MAX_REPORT_ROWS,
    });
    return {
      title: 'Software License Report',
      generatedAt: new Date(),
      columns: [
        { key: 'name', header: 'License', width: 30 },
        { key: 'vendor', header: 'Vendor' },
        { key: 'type', header: 'Type' },
        { key: 'seats', header: 'Seats' },
        { key: 'purchaseCost', header: 'Cost' },
        { key: 'expiryDate', header: 'Expires' },
        { key: 'renewalDate', header: 'Renewal' },
      ],
      // License keys deliberately excluded from exports.
      rows: rows.map(({ licenseKey: _k, ...rest }) => rest) as Array<Record<string, unknown>>,
    };
  }

  private async financial(organizationId: string): Promise<TabularReport> {
    const rows = await this.assets.find({
      where: { organizationId },
      order: { purchaseDate: 'DESC' },
      take: MAX_REPORT_ROWS,
    });
    return {
      title: 'Financial / Depreciation Report',
      generatedAt: new Date(),
      columns: [
        { key: 'assetTag', header: 'Asset Tag' },
        { key: 'name', header: 'Name', width: 30 },
        { key: 'purchaseDate', header: 'Purchase Date' },
        { key: 'purchaseCost', header: 'Purchase Cost' },
        { key: 'usefulLifeYears', header: 'Useful Life (y)' },
        { key: 'annualDepreciation', header: 'Annual Depreciation' },
        { key: 'accumulatedDepreciation', header: 'Accumulated' },
        { key: 'currentBookValue', header: 'Book Value' },
      ],
      rows: rows.map((asset) => {
        const dep = this.assetsService.depreciation(asset);
        return {
          assetTag: asset.assetTag,
          name: asset.name,
          purchaseDate: asset.purchaseDate,
          purchaseCost: asset.purchaseCost,
          usefulLifeYears: dep?.usefulLifeYears ?? asset.usefulLifeYears,
          annualDepreciation: dep?.annualDepreciation ?? null,
          accumulatedDepreciation: dep?.accumulatedDepreciation ?? null,
          currentBookValue: dep?.currentBookValue ?? asset.purchaseCost,
        };
      }),
    };
  }
}

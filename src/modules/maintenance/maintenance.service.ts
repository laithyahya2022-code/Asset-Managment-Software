import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { FindOptionsWhere, Repository } from 'typeorm';
import { Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { TenantCrudService } from '../../common/services/tenant-crud.service';
import { AssetEventType } from '../assets/asset-event.entity';
import { AssetsService } from '../assets/assets.service';
import { CreateMaintenanceDto, UpdateMaintenanceDto } from './maintenance.dto';
import { MaintenanceRecord, MaintenanceStatus } from './maintenance.entity';

@Injectable()
export class MaintenanceService extends TenantCrudService<MaintenanceRecord> {
  constructor(
    @InjectRepository(MaintenanceRecord) repository: Repository<MaintenanceRecord>,
    private readonly assetsService: AssetsService,
  ) {
    super(
      repository,
      'Maintenance record',
      ['title', 'performedBy'],
      ['createdAt', 'scheduledFor', 'completedAt', 'cost', 'status'],
    );
  }

  async listFiltered(
    organizationId: string,
    query: PageQueryDto,
    filters: { assetId?: string; status?: MaintenanceStatus; search?: string },
  ): Promise<Page<MaintenanceRecord>> {
    const where: FindOptionsWhere<MaintenanceRecord> = {};
    if (filters.assetId) where.assetId = filters.assetId;
    if (filters.status) where.status = filters.status;
    return this.list(organizationId, query, filters.search, where);
  }

  async createRecord(
    organizationId: string,
    dto: CreateMaintenanceDto,
    actorUserId: string,
  ): Promise<MaintenanceRecord> {
    const asset = await this.assetsService.findOne(organizationId, dto.assetId);
    const record = await this.create(organizationId, { ...dto, createdById: actorUserId });
    await this.assetsService.recordEvent(
      asset,
      AssetEventType.MAINTENANCE,
      `Maintenance scheduled: ${dto.title} (${dto.type})`,
      actorUserId,
      { maintenanceId: record.id },
    );
    return record;
  }

  async updateRecord(
    organizationId: string,
    id: string,
    dto: UpdateMaintenanceDto,
    actorUserId: string,
  ): Promise<MaintenanceRecord> {
    const record = await this.findOne(organizationId, id);
    if (
      record.status === MaintenanceStatus.COMPLETED ||
      record.status === MaintenanceStatus.CANCELLED
    ) {
      throw new BadRequestException('Closed maintenance records cannot be modified');
    }
    if (dto.assetId && dto.assetId !== record.assetId) {
      throw new BadRequestException('A maintenance record cannot be moved to another asset');
    }

    const statusChanged = dto.status && dto.status !== record.status;
    if (dto.status === MaintenanceStatus.IN_PROGRESS && !record.startedAt) {
      record.startedAt = new Date();
    }
    if (dto.status === MaintenanceStatus.COMPLETED) {
      record.completedAt = new Date();
    }
    Object.assign(record, { ...dto, assetId: record.assetId });
    const saved = await this.repository.save(record);

    if (statusChanged) {
      const asset = await this.assetsService.findOne(organizationId, record.assetId).catch(() => null);
      if (asset) {
        await this.assetsService.recordEvent(
          asset,
          AssetEventType.MAINTENANCE,
          `Maintenance "${record.title}" → ${dto.status}`,
          actorUserId,
          { maintenanceId: record.id, cost: record.cost },
        );
      }
    }
    return saved;
  }

  /** Total maintenance spend for an asset (completed work orders). */
  async costForAsset(organizationId: string, assetId: string): Promise<number> {
    const { sum } = await this.repository
      .createQueryBuilder('m')
      .select('COALESCE(SUM(m.cost), 0)', 'sum')
      .where('m.organizationId = :organizationId', { organizationId })
      .andWhere('m.assetId = :assetId', { assetId })
      .andWhere('m.status = :status', { status: MaintenanceStatus.COMPLETED })
      .getRawOne();
    return Number(sum ?? 0);
  }
}

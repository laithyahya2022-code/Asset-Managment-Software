import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Brackets, Repository } from 'typeorm';
import { buildPage, Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { TenantCrudService } from '../../common/services/tenant-crud.service';
import { AssetCategory } from '../categories/asset-category.entity';
import { AssetEvent, AssetEventType } from './asset-event.entity';
import { assertTransition, AssetStatus } from './asset-lifecycle';
import { Asset } from './asset.entity';
import { AssetFilterDto, CreateAssetDto, TransitionAssetDto, UpdateAssetDto } from './asset.dto';

export interface DepreciationInfo {
  method: 'straight-line';
  purchaseCost: number;
  salvageValue: number;
  usefulLifeYears: number;
  ageYears: number;
  annualDepreciation: number;
  accumulatedDepreciation: number;
  currentBookValue: number;
}

const SORTABLE = ['createdAt', 'assetTag', 'name', 'purchaseDate', 'purchaseCost', 'warrantyEndDate', 'status'];

@Injectable()
export class AssetsService extends TenantCrudService<Asset> {
  constructor(
    @InjectRepository(Asset) repository: Repository<Asset>,
    @InjectRepository(AssetEvent) private readonly events: Repository<AssetEvent>,
    @InjectRepository(AssetCategory) private readonly categories: Repository<AssetCategory>,
  ) {
    super(repository, 'Asset');
  }

  async search(
    organizationId: string,
    query: PageQueryDto,
    filters: AssetFilterDto,
  ): Promise<Page<Asset>> {
    const qb = this.repository
      .createQueryBuilder('asset')
      .where('asset.organizationId = :organizationId', { organizationId });

    if (filters.search) {
      qb.andWhere(
        new Brackets((w) => {
          w.where('LOWER(asset.assetTag) LIKE :s')
            .orWhere('LOWER(asset.name) LIKE :s')
            .orWhere('LOWER(asset.serialNumber) LIKE :s')
            .orWhere('LOWER(asset.manufacturer) LIKE :s')
            .orWhere('LOWER(asset.model) LIKE :s');
        }),
      ).setParameter('s', `%${filters.search.toLowerCase()}%`);
    }
    for (const key of [
      'status',
      'condition',
      'categoryId',
      'branchId',
      'departmentId',
      'supplierId',
      'assignedEmployeeId',
      'manufacturer',
    ] as const) {
      if (filters[key] !== undefined) {
        qb.andWhere(`asset.${key} = :${key}`, { [key]: filters[key] });
      }
    }
    if (filters.warrantyExpiresBefore) {
      qb.andWhere('asset.warrantyEndDate <= :web', { web: filters.warrantyExpiresBefore });
    }
    if (filters.purchasedAfter) {
      qb.andWhere('asset.purchaseDate >= :pa', { pa: filters.purchasedAfter });
    }
    if (filters.purchasedBefore) {
      qb.andWhere('asset.purchaseDate <= :pb', { pb: filters.purchasedBefore });
    }

    const sortBy = query.sortBy && SORTABLE.includes(query.sortBy) ? query.sortBy : 'createdAt';
    qb.orderBy(`asset.${sortBy}`, query.sortOrder)
      .skip((query.page - 1) * query.pageSize)
      .take(query.pageSize);

    const [items, total] = await qb.getManyAndCount();
    return buildPage(items, total, query);
  }

  /** Resolve a scanned QR/barcode payload (asset tag or serial number). */
  async findByCode(organizationId: string, code: string): Promise<Asset> {
    const asset = await this.repository.findOne({
      where: [
        { organizationId, assetTag: code },
        { organizationId, serialNumber: code },
      ],
    });
    if (!asset) throw new NotFoundException(`No asset matches code "${code}"`);
    return asset;
  }

  async createAsset(
    organizationId: string,
    dto: CreateAssetDto,
    actorUserId: string,
    tagPrefix?: string,
  ): Promise<Asset> {
    const category = await this.categories.findOne({
      where: { id: dto.categoryId, organizationId },
    });
    if (!category) throw new BadRequestException('Unknown asset category');
    this.validateCustomFields(category, dto.customFields);

    const assetTag = dto.assetTag ?? (await this.nextAssetTag(organizationId, tagPrefix ?? 'AST'));
    const duplicate = await this.repository.findOne({
      where: { organizationId, assetTag },
      withDeleted: true,
    });
    if (duplicate) throw new BadRequestException(`Asset tag ${assetTag} is already in use`);

    const asset = await this.create(organizationId, {
      ...dto,
      assetTag,
      usefulLifeYears: dto.usefulLifeYears ?? category.usefulLifeYears,
      attachments: dto.attachments?.map((a) => ({ ...a, uploadedAt: new Date().toISOString() })),
    });
    await this.recordEvent(asset, AssetEventType.CREATED, `Asset ${asset.assetTag} created`, actorUserId);
    return asset;
  }

  async updateAsset(
    organizationId: string,
    id: string,
    dto: UpdateAssetDto,
    actorUserId: string,
  ): Promise<Asset> {
    // Lifecycle status changes must go through the transition endpoint so
    // the state machine and side-effects cannot be bypassed.
    const { status: _ignored, assetTag: _tag, ...patch } = dto;

    if (patch.categoryId || patch.customFields) {
      const asset = await this.findOne(organizationId, id);
      const category = await this.categories.findOne({
        where: { id: patch.categoryId ?? asset.categoryId, organizationId },
      });
      if (!category) throw new BadRequestException('Unknown asset category');
      if (patch.customFields) this.validateCustomFields(category, patch.customFields);
    }

    const updated = await this.update(organizationId, id, {
      ...patch,
      attachments: dto.attachments?.map((a: any) => ({
        uploadedAt: new Date().toISOString(),
        ...a,
      })),
    } as Partial<Asset>);
    await this.recordEvent(
      updated,
      AssetEventType.UPDATED,
      `Asset ${updated.assetTag} updated (${Object.keys(patch).join(', ')})`,
      actorUserId,
    );
    return updated;
  }

  async transition(
    organizationId: string,
    id: string,
    dto: TransitionAssetDto,
    actorUserId: string,
  ): Promise<Asset> {
    const asset = await this.findOne(organizationId, id);
    if (asset.status === AssetStatus.ASSIGNED || dto.status === AssetStatus.ASSIGNED) {
      throw new BadRequestException(
        'ASSIGNED is managed by check-out/check-in, not manual transition',
      );
    }
    assertTransition(asset.status, dto.status);

    const from = asset.status;
    asset.status = dto.status;
    if (dto.status === AssetStatus.RETIRED) asset.retiredAt = new Date();
    if (dto.status === AssetStatus.DISPOSED) asset.disposedAt = new Date();
    const saved = await this.repository.save(asset);

    await this.recordEvent(
      saved,
      dto.status === AssetStatus.RETIRED
        ? AssetEventType.RETIRED
        : dto.status === AssetStatus.DISPOSED
          ? AssetEventType.DISPOSED
          : AssetEventType.STATUS_CHANGED,
      `Status changed ${from} → ${dto.status}${dto.reason ? `: ${dto.reason}` : ''}`,
      actorUserId,
      { from, to: dto.status, reason: dto.reason },
    );
    return saved;
  }

  async history(organizationId: string, assetId: string, query: PageQueryDto) {
    await this.findOne(organizationId, assetId); // tenant + existence check
    const [items, total] = await this.events.findAndCount({
      where: { organizationId, assetId },
      order: { createdAt: query.sortOrder },
      skip: (query.page - 1) * query.pageSize,
      take: query.pageSize,
    });
    return buildPage(items, total, query);
  }

  async recordEvent(
    asset: Asset,
    type: AssetEventType,
    description: string,
    actorUserId?: string,
    metadata?: Record<string, unknown>,
  ): Promise<void> {
    await this.events.save(
      this.events.create({
        organizationId: asset.organizationId,
        assetId: asset.id,
        type,
        description,
        actorUserId: actorUserId ?? null,
        metadata: metadata ?? null,
      }),
    );
  }

  /** Straight-line depreciation snapshot; null when cost data is missing. */
  depreciation(asset: Asset, now = new Date()): DepreciationInfo | null {
    if (asset.purchaseCost == null || !asset.purchaseDate) return null;
    const usefulLifeYears = asset.usefulLifeYears ?? 5;
    const salvageValue = asset.salvageValue ?? 0;
    const ageYears = Math.max(
      0,
      (now.getTime() - new Date(asset.purchaseDate).getTime()) / (365.25 * 24 * 3600 * 1000),
    );
    const annualDepreciation = (asset.purchaseCost - salvageValue) / usefulLifeYears;
    const accumulated = Math.min(
      annualDepreciation * ageYears,
      asset.purchaseCost - salvageValue,
    );
    return {
      method: 'straight-line',
      purchaseCost: asset.purchaseCost,
      salvageValue,
      usefulLifeYears,
      ageYears: Number(ageYears.toFixed(2)),
      annualDepreciation: Number(annualDepreciation.toFixed(2)),
      accumulatedDepreciation: Number(accumulated.toFixed(2)),
      currentBookValue: Number((asset.purchaseCost - accumulated).toFixed(2)),
    };
  }

  private validateCustomFields(
    category: AssetCategory,
    values?: Record<string, unknown> | null,
  ): void {
    const defs = category.customFieldDefinitions ?? [];
    const provided = values ?? {};
    const known = new Set(defs.map((d) => d.key));
    for (const key of Object.keys(provided)) {
      if (!known.has(key)) {
        throw new BadRequestException(`Unknown custom field "${key}" for category ${category.name}`);
      }
    }
    for (const def of defs) {
      const value = provided[def.key];
      if (def.required && (value === undefined || value === null || value === '')) {
        throw new BadRequestException(`Custom field "${def.key}" is required`);
      }
      if (value === undefined || value === null) continue;
      const ok =
        (def.type === 'text' && typeof value === 'string') ||
        (def.type === 'number' && typeof value === 'number') ||
        (def.type === 'boolean' && typeof value === 'boolean') ||
        (def.type === 'date' && typeof value === 'string' && !isNaN(Date.parse(value))) ||
        (def.type === 'select' && typeof value === 'string' && (def.options ?? []).includes(value));
      if (!ok) {
        throw new BadRequestException(`Custom field "${def.key}" must be of type ${def.type}`);
      }
    }
  }

  /** Sequential per-tenant tags: PREFIX-000123. */
  private async nextAssetTag(organizationId: string, prefix: string): Promise<string> {
    const count = await this.repository.count({ where: { organizationId }, withDeleted: true });
    for (let i = count + 1; ; i++) {
      const candidate = `${prefix}-${String(i).padStart(6, '0')}`;
      const exists = await this.repository.findOne({
        where: { organizationId, assetTag: candidate },
        withDeleted: true,
      });
      if (!exists) return candidate;
    }
  }
}

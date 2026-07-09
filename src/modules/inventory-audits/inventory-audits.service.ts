import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { FindOptionsWhere, In, Not, Repository } from 'typeorm';
import { buildPage, Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { AssetEventType } from '../assets/asset-event.entity';
import { AssetStatus } from '../assets/asset-lifecycle';
import { Asset } from '../assets/asset.entity';
import { AssetsService } from '../assets/assets.service';
import { InventoryAuditScan } from './inventory-audit-scan.entity';
import {
  InventoryAudit,
  InventoryAuditStatus,
  ScanResult,
} from './inventory-audit.entity';

@Injectable()
export class InventoryAuditsService {
  constructor(
    @InjectRepository(InventoryAudit) private readonly audits: Repository<InventoryAudit>,
    @InjectRepository(InventoryAuditScan)
    private readonly scans: Repository<InventoryAuditScan>,
    @InjectRepository(Asset) private readonly assets: Repository<Asset>,
    private readonly assetsService: AssetsService,
  ) {}

  async list(organizationId: string, query: PageQueryDto): Promise<Page<InventoryAudit>> {
    const [items, total] = await this.audits.findAndCount({
      where: { organizationId },
      order: { startedAt: query.sortOrder },
      skip: (query.page - 1) * query.pageSize,
      take: query.pageSize,
    });
    return buildPage(items, total, query);
  }

  async findOne(organizationId: string, id: string): Promise<InventoryAudit> {
    const audit = await this.audits.findOne({ where: { id, organizationId } });
    if (!audit) throw new NotFoundException('Inventory audit not found');
    return audit;
  }

  /** Start a session, snapshotting the assets expected in scope. */
  async start(
    organizationId: string,
    dto: { name: string; branchId?: string },
    actorUserId: string,
  ): Promise<InventoryAudit> {
    const where: FindOptionsWhere<Asset> = {
      organizationId,
      status: Not(In([AssetStatus.DISPOSED, AssetStatus.PLANNED, AssetStatus.PURCHASE_REQUESTED, AssetStatus.APPROVED, AssetStatus.ORDERED])),
    };
    if (dto.branchId) where.branchId = dto.branchId;
    const expected = await this.assets.find({ where, select: ['id'] });

    return this.audits.save(
      this.audits.create({
        organizationId,
        name: dto.name,
        branchId: dto.branchId ?? null,
        status: InventoryAuditStatus.IN_PROGRESS,
        startedById: actorUserId,
        startedAt: new Date(),
        expectedAssetIds: expected.map((a) => a.id),
      }),
    );
  }

  /** Register a scan; classifies it immediately for live feedback. */
  async scan(
    organizationId: string,
    auditId: string,
    dto: { code: string; locationNote?: string },
    actorUserId: string,
  ): Promise<InventoryAuditScan> {
    const audit = await this.findOne(organizationId, auditId);
    if (audit.status !== InventoryAuditStatus.IN_PROGRESS) {
      throw new BadRequestException('Audit is not in progress');
    }

    let assetId: string | null = null;
    let result: ScanResult = ScanResult.UNKNOWN;

    const asset = await this.assetsService
      .findByCode(organizationId, dto.code)
      .catch(() => null);
    if (asset) {
      assetId = asset.id;
      const alreadyScanned = await this.scans.findOne({
        where: { organizationId, auditId, assetId: asset.id },
      });
      if (alreadyScanned) {
        result = ScanResult.DUPLICATE;
      } else if (audit.expectedAssetIds.includes(asset.id)) {
        result = ScanResult.MATCHED;
      } else {
        // Exists in the tenant but not in this audit's scope → moved here.
        result = ScanResult.WRONG_LOCATION;
      }
    }

    return this.scans.save(
      this.scans.create({
        organizationId,
        auditId,
        scannedCode: dto.code,
        assetId,
        result,
        scannedById: actorUserId,
        scannedAt: new Date(),
        locationNote: dto.locationNote,
      }),
    );
  }

  listScans(organizationId: string, auditId: string, query: PageQueryDto) {
    return this.scans
      .findAndCount({
        where: { organizationId, auditId },
        order: { scannedAt: 'DESC' },
        skip: (query.page - 1) * query.pageSize,
        take: query.pageSize,
      })
      .then(([items, total]) => buildPage(items, total, query));
  }

  /** Close the session and compute missing / moved / unknown. */
  async complete(
    organizationId: string,
    auditId: string,
    actorUserId: string,
  ): Promise<InventoryAudit> {
    const audit = await this.findOne(organizationId, auditId);
    if (audit.status !== InventoryAuditStatus.IN_PROGRESS) {
      throw new BadRequestException('Audit is not in progress');
    }

    const scans = await this.scans.find({ where: { organizationId, auditId } });
    const scannedAssetIds = new Set(
      scans.filter((s) => s.assetId).map((s) => s.assetId as string),
    );

    const missingAssetIds = audit.expectedAssetIds.filter((id) => !scannedAssetIds.has(id));
    const wrongLocationAssetIds = [
      ...new Set(
        scans
          .filter((s) => s.result === ScanResult.WRONG_LOCATION && s.assetId)
          .map((s) => s.assetId as string),
      ),
    ];
    const unknownCodes = [
      ...new Set(scans.filter((s) => s.result === ScanResult.UNKNOWN).map((s) => s.scannedCode)),
    ];

    audit.status = InventoryAuditStatus.COMPLETED;
    audit.completedAt = new Date();
    audit.results = {
      expected: audit.expectedAssetIds.length,
      scanned: scans.length,
      matched: scans.filter((s) => s.result === ScanResult.MATCHED).length,
      missingAssetIds,
      wrongLocationAssetIds,
      unknownCodes,
    };
    const saved = await this.audits.save(audit);

    // Stamp an AUDITED event on every verified asset.
    for (const id of scannedAssetIds) {
      const asset = await this.assets.findOne({ where: { id, organizationId } });
      if (asset) {
        await this.assetsService.recordEvent(
          asset,
          AssetEventType.AUDITED,
          `Verified in inventory audit "${audit.name}"`,
          actorUserId,
          { auditId: audit.id },
        );
      }
    }
    return saved;
  }

  async cancel(organizationId: string, auditId: string): Promise<InventoryAudit> {
    const audit = await this.findOne(organizationId, auditId);
    if (audit.status !== InventoryAuditStatus.IN_PROGRESS) {
      throw new BadRequestException('Audit is not in progress');
    }
    audit.status = InventoryAuditStatus.CANCELLED;
    audit.completedAt = new Date();
    return this.audits.save(audit);
  }
}

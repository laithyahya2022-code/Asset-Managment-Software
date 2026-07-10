import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { FindOptionsWhere, Repository } from 'typeorm';
import { buildPage, Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { AuditLog } from './audit-log.entity';

const SENSITIVE_KEYS = /password|secret|token|signature|licensekey/i;

/** Redact sensitive values before they reach the audit store. */
export const sanitizeForAudit = (
  body: Record<string, unknown> | undefined | null,
): Record<string, unknown> | null => {
  if (!body || typeof body !== 'object') return null;
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(body)) {
    out[key] = SENSITIVE_KEYS.test(key) ? '[REDACTED]' : value;
  }
  return out;
};

@Injectable()
export class AuditLogService {
  private readonly logger = new Logger(AuditLogService.name);

  constructor(
    @InjectRepository(AuditLog)
    private readonly repository: Repository<AuditLog>,
  ) {}

  /**
   * Fire-and-forget by design: an audit insert failure must never break
   * the business operation it describes, but it is always logged.
   */
  async record(entry: Partial<AuditLog>): Promise<void> {
    try {
      await this.repository.save(this.repository.create(entry));
    } catch (error) {
      this.logger.error(`Failed to write audit log entry: ${(error as Error).message}`);
    }
  }

  async list(
    organizationId: string,
    query: PageQueryDto,
    filters: { action?: string; entityType?: string; entityId?: string; actorUserId?: string },
  ): Promise<Page<AuditLog>> {
    const where: FindOptionsWhere<AuditLog> = { organizationId };
    if (filters.action) where.action = filters.action;
    if (filters.entityType) where.entityType = filters.entityType;
    if (filters.entityId) where.entityId = filters.entityId;
    if (filters.actorUserId) where.actorUserId = filters.actorUserId;

    const [items, total] = await this.repository.findAndCount({
      where,
      order: { createdAt: query.sortOrder },
      skip: (query.page - 1) * query.pageSize,
      take: query.pageSize,
    });
    return buildPage(items, total, query);
  }
}

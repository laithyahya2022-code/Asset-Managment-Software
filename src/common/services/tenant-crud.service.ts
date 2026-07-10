import { NotFoundException } from '@nestjs/common';
import { DeepPartial, FindOptionsWhere, ILike, Repository } from 'typeorm';
import { TenantBaseEntity } from '../entities/tenant-base.entity';
import { buildPage, Page, PageQueryDto } from '../dto/page-query.dto';

/**
 * Reusable tenant-scoped CRUD building block (repository pattern).
 *
 * Every read and write is constrained by `organizationId`, which makes
 * cross-tenant access impossible even if a caller guesses a foreign UUID —
 * the row simply resolves to 404 within their tenant.
 */
export abstract class TenantCrudService<T extends TenantBaseEntity> {
  protected constructor(
    protected readonly repository: Repository<T>,
    protected readonly entityName: string,
    /** Columns searched by the free-text `search` list parameter. */
    protected readonly searchColumns: (keyof T & string)[] = [],
    /** Columns callers are allowed to sort by. */
    protected readonly sortableColumns: (keyof T & string)[] = ['createdAt' as keyof T & string],
  ) {}

  async list(
    organizationId: string,
    query: PageQueryDto,
    search?: string,
    extraWhere: FindOptionsWhere<T> = {} as FindOptionsWhere<T>,
  ): Promise<Page<T>> {
    const base = { ...extraWhere, organizationId } as FindOptionsWhere<T>;
    const where: FindOptionsWhere<T>[] =
      search && this.searchColumns.length > 0
        ? this.searchColumns.map((col) => ({ ...base, [col]: ILike(`%${search}%`) }))
        : [base];

    const sortBy =
      query.sortBy && this.sortableColumns.includes(query.sortBy as keyof T & string)
        ? query.sortBy
        : 'createdAt';

    const [items, total] = await this.repository.findAndCount({
      where,
      order: { [sortBy]: query.sortOrder } as any,
      skip: (query.page - 1) * query.pageSize,
      take: query.pageSize,
    });
    return buildPage(items, total, query);
  }

  async findOne(organizationId: string, id: string): Promise<T> {
    const entity = await this.repository.findOne({
      where: { id, organizationId } as FindOptionsWhere<T>,
    });
    if (!entity) throw new NotFoundException(`${this.entityName} not found`);
    return entity;
  }

  async create(organizationId: string, dto: DeepPartial<T>): Promise<T> {
    const entity = this.repository.create({ ...dto, organizationId } as DeepPartial<T>);
    return this.repository.save(entity);
  }

  async update(organizationId: string, id: string, dto: DeepPartial<T>): Promise<T> {
    const entity = await this.findOne(organizationId, id);
    // organizationId is immutable; never allow it to travel in an update.
    const { organizationId: _ignored, id: _id, ...patch } = dto as any;
    Object.assign(entity, patch);
    return this.repository.save(entity);
  }

  async softDelete(organizationId: string, id: string): Promise<void> {
    const entity = await this.findOne(organizationId, id);
    await this.repository.softRemove(entity);
  }
}

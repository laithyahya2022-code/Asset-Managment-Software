import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { DataSource, FindOptionsWhere, IsNull, LessThan, Repository } from 'typeorm';
import { buildPage, Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { AssetEvent, AssetEventType } from '../assets/asset-event.entity';
import { AssetCondition, AssetStatus, CHECKOUTABLE_STATUSES } from '../assets/asset-lifecycle';
import { Asset } from '../assets/asset.entity';
import { Employee } from '../employees/employee.entity';
import { AssetAssignment, AssignmentStatus } from './assignment.entity';
import { CheckInDto, CheckOutDto } from './assignment.dto';

@Injectable()
export class AssignmentsService {
  constructor(
    @InjectRepository(AssetAssignment)
    private readonly assignments: Repository<AssetAssignment>,
    @InjectRepository(Asset) private readonly assets: Repository<Asset>,
    @InjectRepository(Employee) private readonly employees: Repository<Employee>,
    private readonly dataSource: DataSource,
  ) {}

  async list(
    organizationId: string,
    query: PageQueryDto,
    filters: { assetId?: string; employeeId?: string; status?: AssignmentStatus; overdue?: boolean },
  ): Promise<Page<AssetAssignment>> {
    const where: FindOptionsWhere<AssetAssignment> = { organizationId };
    if (filters.assetId) where.assetId = filters.assetId;
    if (filters.employeeId) where.employeeId = filters.employeeId;
    if (filters.status) where.status = filters.status;
    if (filters.overdue) {
      where.status = AssignmentStatus.ACTIVE;
      where.expectedReturnAt = LessThan(new Date());
      where.returnedAt = IsNull();
    }
    const [items, total] = await this.assignments.findAndCount({
      where,
      order: { checkedOutAt: query.sortOrder },
      skip: (query.page - 1) * query.pageSize,
      take: query.pageSize,
    });
    return buildPage(items, total, query);
  }

  async findOne(organizationId: string, id: string): Promise<AssetAssignment> {
    const assignment = await this.assignments.findOne({ where: { id, organizationId } });
    if (!assignment) throw new NotFoundException('Assignment not found');
    return assignment;
  }

  /**
   * Hand an asset to an employee. Atomic: the assignment record, the
   * asset's status/holder and its history event commit together.
   */
  async checkOut(
    organizationId: string,
    dto: CheckOutDto,
    actorUserId: string,
  ): Promise<AssetAssignment> {
    return this.dataSource.transaction(async (manager) => {
      const asset = await manager.findOne(Asset, {
        where: { id: dto.assetId, organizationId },
        lock: manager.connection.options.type === 'postgres' ? { mode: 'pessimistic_write' } : undefined,
      });
      if (!asset) throw new NotFoundException('Asset not found');
      if (!CHECKOUTABLE_STATUSES.includes(asset.status)) {
        throw new BadRequestException(
          `Asset is ${asset.status}; only ${CHECKOUTABLE_STATUSES.join(', ')} assets can be checked out`,
        );
      }

      const employee = await manager.findOne(Employee, {
        where: { id: dto.employeeId, organizationId },
      });
      if (!employee) throw new NotFoundException('Employee not found');
      if (!employee.isActive) throw new BadRequestException('Employee is inactive');

      const assignment = await manager.save(
        manager.create(AssetAssignment, {
          organizationId,
          assetId: asset.id,
          employeeId: employee.id,
          status: AssignmentStatus.ACTIVE,
          checkedOutById: actorUserId,
          checkedOutAt: new Date(),
          expectedReturnAt: dto.expectedReturnAt ? new Date(dto.expectedReturnAt) : null,
          checkoutCondition: dto.condition ?? asset.condition,
          checkoutSignature: dto.signature ?? null,
          checkoutNotes: dto.notes,
          photos: dto.photos ?? null,
        }),
      );

      asset.status = AssetStatus.ASSIGNED;
      asset.assignedEmployeeId = employee.id;
      if (dto.condition) asset.condition = dto.condition;
      await manager.save(asset);

      await manager.save(
        manager.create(AssetEvent, {
          organizationId,
          assetId: asset.id,
          type: AssetEventType.CHECKED_OUT,
          description: `Checked out to ${employee.fullName} (${employee.employeeNumber})`,
          actorUserId,
          metadata: { assignmentId: assignment.id, employeeId: employee.id },
        }),
      );
      return assignment;
    });
  }

  /** Take an asset back, recording condition, damage and signature. */
  async checkIn(
    organizationId: string,
    assignmentId: string,
    dto: CheckInDto,
    actorUserId: string,
  ): Promise<AssetAssignment> {
    return this.dataSource.transaction(async (manager) => {
      const assignment = await manager.findOne(AssetAssignment, {
        where: { id: assignmentId, organizationId },
      });
      if (!assignment) throw new NotFoundException('Assignment not found');
      if (assignment.status !== AssignmentStatus.ACTIVE) {
        throw new BadRequestException('Assignment is already closed');
      }

      assignment.status = AssignmentStatus.RETURNED;
      assignment.returnedAt = new Date();
      assignment.checkedInById = actorUserId;
      assignment.checkinCondition = dto.condition ?? null;
      assignment.checkinSignature = dto.signature ?? null;
      assignment.damageNotes = dto.damageNotes;
      if (dto.photos?.length) {
        assignment.photos = [...(assignment.photos ?? []), ...dto.photos];
      }
      await manager.save(assignment);

      const asset = await manager.findOne(Asset, {
        where: { id: assignment.assetId, organizationId },
      });
      if (asset) {
        asset.status = AssetStatus.IN_STOCK;
        asset.assignedEmployeeId = null;
        if (dto.condition) asset.condition = dto.condition;
        await manager.save(asset);
        await manager.save(
          manager.create(AssetEvent, {
            organizationId,
            assetId: asset.id,
            type: AssetEventType.CHECKED_IN,
            description: `Checked in${dto.condition ? ` in ${dto.condition} condition` : ''}${
              dto.damageNotes ? ` — damage: ${dto.damageNotes}` : ''
            }`,
            actorUserId,
            metadata: { assignmentId: assignment.id },
          }),
        );
      }
      return assignment;
    });
  }

  /** Active assignments past their expected return date. */
  findOverdue(organizationId?: string): Promise<AssetAssignment[]> {
    const where: FindOptionsWhere<AssetAssignment> = {
      status: AssignmentStatus.ACTIVE,
      expectedReturnAt: LessThan(new Date()),
      returnedAt: IsNull(),
    };
    if (organizationId) where.organizationId = organizationId;
    return this.assignments.find({ where });
  }

  async markOverdueNotified(ids: string[]): Promise<void> {
    if (ids.length > 0) {
      await this.assignments.update(ids, { overdueNotified: true });
    }
  }

  /** Self-service: the assets currently held by a given employee. */
  async assetsHeldBy(organizationId: string, employeeId: string): Promise<Asset[]> {
    return this.assets.find({
      where: { organizationId, assignedEmployeeId: employeeId },
      order: { assetTag: 'ASC' },
    });
  }
}

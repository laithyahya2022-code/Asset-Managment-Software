import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { IsNull, Repository } from 'typeorm';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { TenantCrudService } from '../../common/services/tenant-crud.service';
import { Asset } from '../assets/asset.entity';
import { Employee } from '../employees/employee.entity';
import { AssignLicenseDto } from './license.dto';
import { LicenseAssignment } from './license-assignment.entity';
import { SoftwareLicense } from './license.entity';

export interface LicenseWithUsage extends SoftwareLicense {
  seatsUsed: number;
  seatsRemaining: number;
}

@Injectable()
export class LicensesService extends TenantCrudService<SoftwareLicense> {
  constructor(
    @InjectRepository(SoftwareLicense) repository: Repository<SoftwareLicense>,
    @InjectRepository(LicenseAssignment)
    private readonly licenseAssignments: Repository<LicenseAssignment>,
    @InjectRepository(Asset) private readonly assets: Repository<Asset>,
    @InjectRepository(Employee) private readonly employees: Repository<Employee>,
  ) {
    super(
      repository,
      'License',
      ['name', 'vendor'],
      ['createdAt', 'name', 'vendor', 'expiryDate', 'seats'],
    );
  }

  async withUsage(license: SoftwareLicense): Promise<LicenseWithUsage> {
    const seatsUsed = await this.licenseAssignments.count({
      where: { licenseId: license.id, organizationId: license.organizationId, releasedAt: IsNull() },
    });
    return { ...license, seatsUsed, seatsRemaining: license.seats - seatsUsed };
  }

  async assignSeat(
    organizationId: string,
    licenseId: string,
    dto: AssignLicenseDto,
    actorUserId: string,
  ): Promise<LicenseAssignment> {
    if (!dto.assetId && !dto.employeeId) {
      throw new BadRequestException('Provide assetId and/or employeeId');
    }
    const license = await this.findOne(organizationId, licenseId);
    const usage = await this.withUsage(license);
    if (usage.seatsRemaining <= 0) {
      throw new BadRequestException('No seats remaining on this license');
    }
    if (dto.assetId) {
      const asset = await this.assets.findOne({ where: { id: dto.assetId, organizationId } });
      if (!asset) throw new NotFoundException('Asset not found');
    }
    if (dto.employeeId) {
      const employee = await this.employees.findOne({
        where: { id: dto.employeeId, organizationId },
      });
      if (!employee) throw new NotFoundException('Employee not found');
    }
    const duplicate = await this.licenseAssignments.findOne({
      where: {
        organizationId,
        licenseId,
        releasedAt: IsNull(),
        assetId: dto.assetId ?? IsNull(),
        employeeId: dto.employeeId ?? IsNull(),
      },
    });
    if (duplicate) throw new BadRequestException('Seat already assigned to this target');

    return this.licenseAssignments.save(
      this.licenseAssignments.create({
        organizationId,
        licenseId,
        assetId: dto.assetId ?? null,
        employeeId: dto.employeeId ?? null,
        assignedById: actorUserId,
        assignedAt: new Date(),
      }),
    );
  }

  async releaseSeat(organizationId: string, licenseId: string, seatId: string): Promise<void> {
    const seat = await this.licenseAssignments.findOne({
      where: { id: seatId, licenseId, organizationId },
    });
    if (!seat) throw new NotFoundException('Seat assignment not found');
    if (seat.releasedAt) throw new BadRequestException('Seat already released');
    seat.releasedAt = new Date();
    await this.licenseAssignments.save(seat);
  }

  listSeats(organizationId: string, licenseId: string, query: PageQueryDto) {
    return this.licenseAssignments
      .findAndCount({
        where: { organizationId, licenseId },
        order: { assignedAt: 'DESC' },
        skip: (query.page - 1) * query.pageSize,
        take: query.pageSize,
      })
      .then(([items, total]) => ({
        items,
        total,
        page: query.page,
        pageSize: query.pageSize,
        totalPages: Math.max(1, Math.ceil(total / query.pageSize)),
      }));
  }
}

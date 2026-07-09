import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { AssignLicenseDto, CreateLicenseDto, UpdateLicenseDto } from './license.dto';
import { LicensesService } from './licenses.service';

const [READ, CREATE, UPDATE, DELETE] = PERMISSIONS.LICENSES;

@ApiTags('Software Licenses')
@ApiBearerAuth()
@Controller('licenses')
export class LicensesController {
  constructor(private readonly service: LicensesService) {}

  @Get()
  @RequirePermissions(READ)
  async list(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PageQueryDto,
    @Query('search') search?: string,
  ) {
    const page = await this.service.list(user.organizationId, query, search);
    // License keys never appear in list views.
    return {
      ...page,
      items: await Promise.all(
        page.items.map(async (l) => {
          const { licenseKey: _hidden, ...rest } = await this.service.withUsage(l);
          return rest;
        }),
      ),
    };
  }

  @Get(':id')
  @RequirePermissions(READ)
  async findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.withUsage(await this.service.findOne(user.organizationId, id));
  }

  @Get(':id/seats')
  @RequirePermissions(READ)
  seats(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Query() query: PageQueryDto,
  ) {
    return this.service.listSeats(user.organizationId, id, query);
  }

  @Post()
  @RequirePermissions(CREATE)
  create(@CurrentUser() user: AuthenticatedUser, @Body() dto: CreateLicenseDto) {
    return this.service.create(user.organizationId, dto);
  }

  @Patch(':id')
  @RequirePermissions(UPDATE)
  update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateLicenseDto,
  ) {
    return this.service.update(user.organizationId, id, dto);
  }

  @Post(':id/assign')
  @RequirePermissions(PERMISSIONS.LICENSES_ASSIGN)
  @ApiOperation({ summary: 'Consume a seat for a device and/or user' })
  assign(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: AssignLicenseDto,
  ) {
    return this.service.assignSeat(user.organizationId, id, dto, user.userId);
  }

  @Post(':id/seats/:seatId/release')
  @HttpCode(204)
  @RequirePermissions(PERMISSIONS.LICENSES_ASSIGN)
  release(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Param('seatId', ParseUUIDPipe) seatId: string,
  ) {
    return this.service.releaseSeat(user.organizationId, id, seatId);
  }

  @Delete(':id')
  @HttpCode(204)
  @RequirePermissions(DELETE)
  remove(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.softDelete(user.organizationId, id);
  }
}

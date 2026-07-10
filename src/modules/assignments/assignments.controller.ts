import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
  Query,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { AssignmentStatus } from './assignment.entity';
import { CheckInDto, CheckOutDto } from './assignment.dto';
import { AssignmentsService } from './assignments.service';

@ApiTags('Check-In / Check-Out')
@ApiBearerAuth()
@Controller('assignments')
export class AssignmentsController {
  constructor(private readonly service: AssignmentsService) {}

  @Get()
  @RequirePermissions(PERMISSIONS.ASSIGNMENTS_READ)
  list(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PageQueryDto,
    @Query('assetId') assetId?: string,
    @Query('employeeId') employeeId?: string,
    @Query('status') status?: AssignmentStatus,
    @Query('overdue') overdue?: string,
  ) {
    return this.service.list(user.organizationId, query, {
      assetId,
      employeeId,
      status,
      overdue: overdue === 'true',
    });
  }

  @Get('employee/:employeeId/assets')
  @RequirePermissions(PERMISSIONS.ASSIGNMENTS_READ)
  @ApiOperation({ summary: 'Assets currently held by an employee' })
  assetsHeldBy(
    @CurrentUser() user: AuthenticatedUser,
    @Param('employeeId', ParseUUIDPipe) employeeId: string,
  ) {
    return this.service.assetsHeldBy(user.organizationId, employeeId);
  }

  @Get(':id')
  @RequirePermissions(PERMISSIONS.ASSIGNMENTS_READ)
  findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(user.organizationId, id);
  }

  @Post('check-out')
  @RequirePermissions(PERMISSIONS.ASSIGNMENTS_CHECKOUT)
  @ApiOperation({ summary: 'Assign an asset to an employee (with signature)' })
  checkOut(@CurrentUser() user: AuthenticatedUser, @Body() dto: CheckOutDto) {
    return this.service.checkOut(user.organizationId, dto, user.userId);
  }

  @Post(':id/check-in')
  @RequirePermissions(PERMISSIONS.ASSIGNMENTS_CHECKIN)
  @ApiOperation({ summary: 'Return an asset (condition, damage notes, signature)' })
  checkIn(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: CheckInDto,
  ) {
    return this.service.checkIn(user.organizationId, id, dto, user.userId);
  }
}

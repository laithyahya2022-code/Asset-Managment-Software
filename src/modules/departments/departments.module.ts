import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  Injectable,
  Module,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { InjectRepository, TypeOrmModule } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { TenantCrudService } from '../../common/services/tenant-crud.service';
import { CreateDepartmentDto, UpdateDepartmentDto } from './department.dto';
import { Department } from './department.entity';

const [READ, CREATE, UPDATE, DELETE] = PERMISSIONS.DEPARTMENTS;

@Injectable()
export class DepartmentsService extends TenantCrudService<Department> {
  constructor(@InjectRepository(Department) repository: Repository<Department>) {
    super(repository, 'Department', ['name', 'code'], ['createdAt', 'name', 'code']);
  }
}

@ApiTags('Departments')
@ApiBearerAuth()
@Controller('departments')
export class DepartmentsController {
  constructor(private readonly service: DepartmentsService) {}

  @Get()
  @RequirePermissions(READ)
  list(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PageQueryDto,
    @Query('search') search?: string,
  ) {
    return this.service.list(user.organizationId, query, search);
  }

  @Get(':id')
  @RequirePermissions(READ)
  findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(user.organizationId, id);
  }

  @Post()
  @RequirePermissions(CREATE)
  create(@CurrentUser() user: AuthenticatedUser, @Body() dto: CreateDepartmentDto) {
    return this.service.create(user.organizationId, dto);
  }

  @Patch(':id')
  @RequirePermissions(UPDATE)
  update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateDepartmentDto,
  ) {
    return this.service.update(user.organizationId, id, dto);
  }

  @Delete(':id')
  @HttpCode(204)
  @RequirePermissions(DELETE)
  remove(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.softDelete(user.organizationId, id);
  }
}

@Module({
  imports: [TypeOrmModule.forFeature([Department])],
  controllers: [DepartmentsController],
  providers: [DepartmentsService],
  exports: [DepartmentsService],
})
export class DepartmentsModule {}

import { ApiProperty, ApiPropertyOptional, PartialType } from '@nestjs/swagger';
import {
  IsDateString,
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsNumber,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
  Min,
} from 'class-validator';
import { LicenseType } from './license.entity';

export class CreateLicenseDto {
  @ApiProperty({ example: 'Microsoft 365 E3' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  name: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(200)
  vendor?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(500)
  licenseKey?: string;

  @ApiPropertyOptional({ enum: LicenseType, default: LicenseType.SUBSCRIPTION })
  @IsOptional()
  @IsEnum(LicenseType)
  type?: LicenseType;

  @ApiPropertyOptional({ default: 1 })
  @IsOptional()
  @IsInt()
  @Min(1)
  seats?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsDateString()
  purchaseDate?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  @Min(0)
  purchaseCost?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsUUID()
  supplierId?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsDateString()
  expiryDate?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsDateString()
  renewalDate?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(2000)
  notes?: string;
}

export class UpdateLicenseDto extends PartialType(CreateLicenseDto) {}

export class AssignLicenseDto {
  @ApiPropertyOptional({ description: 'Device consuming the seat' })
  @IsOptional()
  @IsUUID()
  assetId?: string;

  @ApiPropertyOptional({ description: 'User consuming the seat' })
  @IsOptional()
  @IsUUID()
  employeeId?: string;
}

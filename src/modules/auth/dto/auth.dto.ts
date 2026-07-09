import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsEmail,
  IsNotEmpty,
  IsOptional,
  IsString,
  Matches,
  MaxLength,
  MinLength,
} from 'class-validator';

export class RegisterOrganizationDto {
  @ApiProperty({ example: 'Acme Corporation' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  organizationName: string;

  @ApiProperty({ example: 'acme', description: 'URL-safe unique tenant identifier' })
  @IsString()
  @Matches(/^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$/, {
    message: 'slug must be lowercase alphanumeric with dashes',
  })
  organizationSlug: string;

  @ApiProperty({ example: 'admin@acme.com' })
  @IsEmail()
  adminEmail: string;

  @ApiProperty({ example: 'Jane Admin' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  adminFullName: string;

  @ApiProperty({ minLength: 10, example: 'Str0ng!Passphrase' })
  @IsString()
  @MinLength(10)
  @MaxLength(128)
  adminPassword: string;
}

export class LoginDto {
  @ApiProperty({ example: 'admin@acme.com' })
  @IsEmail()
  email: string;

  @ApiProperty()
  @IsString()
  @IsNotEmpty()
  password: string;

  @ApiPropertyOptional({
    description: 'Tenant slug; required only when the email exists in several tenants',
  })
  @IsOptional()
  @IsString()
  organizationSlug?: string;
}

export class RefreshTokenDto {
  @ApiProperty()
  @IsString()
  @IsNotEmpty()
  refreshToken: string;
}

export class ChangePasswordDto {
  @ApiProperty()
  @IsString()
  @IsNotEmpty()
  currentPassword: string;

  @ApiProperty({ minLength: 10 })
  @IsString()
  @MinLength(10)
  @MaxLength(128)
  newPassword: string;
}

import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';

export interface AccessTokenPayload {
  sub: string;
  org: string;
  email: string;
  name: string;
  roleId: string;
  roleName: string;
  permissions: string[];
}

/**
 * Stateless access-token validation. Tokens are short-lived (15 min by
 * default); revocation happens at the refresh boundary, where the stored
 * refresh-token hash is checked and rotated.
 */
@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: config.get<string>('jwt.secret')!,
    });
  }

  validate(payload: AccessTokenPayload): AuthenticatedUser {
    return {
      userId: payload.sub,
      organizationId: payload.org,
      email: payload.email,
      fullName: payload.name,
      roleId: payload.roleId,
      roleName: payload.roleName,
      permissions: payload.permissions ?? [],
    };
  }
}

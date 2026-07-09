import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common';
import { Observable, tap } from 'rxjs';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { AuditLogService, sanitizeForAudit } from './audit-log.service';

const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
const ACTION_BY_METHOD: Record<string, string> = {
  POST: 'created',
  PUT: 'updated',
  PATCH: 'updated',
  DELETE: 'deleted',
};

/**
 * Cross-cutting audit trail: records every successful mutating request
 * with actor, tenant, target entity and a redacted payload snapshot.
 * Domain services add richer, business-level entries on top of this.
 */
@Injectable()
export class AuditLogInterceptor implements NestInterceptor {
  constructor(private readonly auditLogService: AuditLogService) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const request = context.switchToHttp().getRequest();
    if (!MUTATING.has(request.method)) return next.handle();

    return next.handle().pipe(
      tap((responseBody) => {
        const user: AuthenticatedUser | undefined = request.user;
        // Path shape: /api/v1/<resource>/... — resource is the entity type.
        const segments: string[] = request.path.split('/').filter(Boolean);
        const resource = segments[2] ?? segments[segments.length - 1] ?? 'unknown';
        const subAction = segments.slice(3).find((s) => !/^[0-9a-f-]{36}$/i.test(s));

        void this.auditLogService.record({
          organizationId: user?.organizationId ?? null,
          actorUserId: user?.userId ?? null,
          actorEmail: user?.email ?? null,
          action: `${resource}.${subAction ?? ACTION_BY_METHOD[request.method]}`,
          entityType: resource,
          entityId: request.params?.id ?? (responseBody as any)?.id ?? null,
          statusCode: context.switchToHttp().getResponse().statusCode,
          ipAddress: request.ip,
          metadata: sanitizeForAudit(request.body),
        });
      }),
    );
  }
}

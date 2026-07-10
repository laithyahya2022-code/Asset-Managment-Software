import 'reflect-metadata';
import { ClassSerializerInterceptor, Logger, ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory, Reflector } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import helmet from 'helmet';
import { join } from 'path';
import { AppModule } from './app.module';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, { bufferLogs: false });
  const config = app.get(ConfigService);
  const prefix = config.get<string>('globalPrefix') ?? 'api/v1';

  app.setGlobalPrefix(prefix);
  app.use(
    helmet({
      contentSecurityPolicy: {
        useDefaults: true,
        // blob: lets the web client render authenticated QR/barcode PNGs.
        directives: { 'img-src': ["'self'", 'data:', 'blob:'] },
      },
    }),
  );
  // Built-in web client (public/) served at the root, API under /api/v1.
  app.useStaticAssets(join(__dirname, '..', 'public'));
  app.enableCors({ origin: process.env.CORS_ORIGINS?.split(',') ?? true, credentials: true });
  app.useGlobalPipes(
    new ValidationPipe({
      // Unknown properties are silently stripped (not rejected): list
      // endpoints validate the same query string against several DTOs.
      whitelist: true,
      transform: true,
      transformOptions: { enableImplicitConversion: false },
    }),
  );
  app.useGlobalInterceptors(new ClassSerializerInterceptor(app.get(Reflector)));
  app.useGlobalFilters(new HttpExceptionFilter());
  app.enableShutdownHooks();

  const swagger = new DocumentBuilder()
    .setTitle('ITAM Platform API')
    .setDescription(
      'Enterprise cloud-based IT Asset Management platform — multi-tenant REST API. ' +
        'Authenticate via POST /auth/login and use the Bearer token.',
    )
    .setVersion('0.1.0')
    .addBearerAuth()
    .build();
  SwaggerModule.setup(`${prefix}/docs`, app, SwaggerModule.createDocument(app, swagger));

  const port = config.get<number>('port') ?? 3000;
  await app.listen(port);
  new Logger('Bootstrap').log(
    `ITAM Platform listening on :${port} — web app at /, API docs at /${prefix}/docs`,
  );
}

void bootstrap();

import 'reflect-metadata';
import { ClassSerializerInterceptor, Logger, ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory, Reflector } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import helmet from 'helmet';
import { AppModule } from './app.module';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule, { bufferLogs: false });
  const config = app.get(ConfigService);
  const prefix = config.get<string>('globalPrefix') ?? 'api/v1';

  app.setGlobalPrefix(prefix);
  app.use(helmet());
  app.enableCors({ origin: process.env.CORS_ORIGINS?.split(',') ?? true, credentials: true });
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true, // strip unknown properties
      forbidNonWhitelisted: true, // …and reject requests that send them
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
  new Logger('Bootstrap').log(`ITAM API listening on :${port} (docs at /${prefix}/docs)`);
}

void bootstrap();

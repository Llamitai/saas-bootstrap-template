## Why

La release bloqueada por falta de Redis en CI llevó a revisar la infraestructura
de datos efímeros. El usuario decidió (2026-09-27) usar Valkey para caché con
una configuración orientada al rendimiento y RabbitMQ para las colas con una
configuración orientada a la estabilidad. Hoy SAQ usa el mismo Redis para las
colas: un reinicio o una expulsión de memoria pierden trabajos y no hay reintentos
acotados ni dead-letter.

Consumidores: quien encola comandos asíncronos (invitaciones, emails, borrados),
quien opera el worker y quien despliega los proyectos generados.

## What Changes

- Valkey 9 sustituye a Redis (mismo protocolo; se mantienen el hostname `redis`
  y los ajustes `REDIS_*`) con configuración de rendimiento que no expulsa claves
  de seguridad.
- RabbitMQ sustituye a SAQ: publicación persistente con confirmaciones, cola
  quorum, reintentos acotados y dead-letter, worker con ack manual y apagado
  ordenado.
- CI, preflight de template y stacks de desarrollo levantan Valkey y RabbitMQ.

## Capabilities

### New Capabilities

- `background-queue`: entrega fiable de comandos asíncronos.
- `cache-store`: almacén de tokens, límites y caché.

### Modified Capabilities

Ninguna spec vigente cambia.

## Impact

Backend (buses, lifespan, worker, settings), compose, Dockerfile/commands, CI,
template preflight y documentación. Los proyectos generados necesitan un
RabbitMQ y variables `RABBITMQ_*` en producción: migración manual.

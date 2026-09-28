---
title: "0009 — Valkey para caché y RabbitMQ para colas"
---

Estado: aceptado por decisión del usuario, 2026-09-27. Reemplaza a Redis y SAQ.
Change: `adopt-valkey-and-rabbitmq`.

## Contexto y drivers

Redis cumplía dos papeles con requisitos opuestos:

- **Estado efímero de alta frecuencia:** lista negra de refresh tokens, rotación
  idempotente y contadores de rate limit. Necesita latencia baja.
- **Cola de trabajos (SAQ):** comandos asíncronos como emails o borrados. Necesita
  no perder trabajos, reintentar de forma acotada y apartar los que fallan
  siempre.

Con SAQ sobre Redis, una expulsión de memoria o un reinicio sin persistencia
pierden trabajos, y no hay dead-letter. El release `v0.6.0` quedó bloqueado
porque CI no levantaba Redis, lo que obligó a revisar esta infraestructura.

Drivers: rendimiento para la caché, estabilidad para las colas, y que ninguna
optimización de rendimiento reabra un token revocado. La lista negra de refresh
tokens obligaba a `noeviction` y a persistencia, y crecía con cada rotación.

## Opciones

1. Mantener Redis y SAQ, añadiendo persistencia.
2. Valkey para caché y SAQ sobre Valkey.
3. Valkey para caché y RabbitMQ para colas.

## Decisión

Opción 3.

- **Valkey 9** sustituye a Redis. Habla el mismo protocolo, así que se mantienen
  el cliente `redis-py`, el hostname `redis` y los ajustes `REDIS_*`. La
  configuración prioriza el rendimiento: `io-threads`, lazyfree, sin snapshots
  RDB y `maxmemory-policy allkeys-lru`.
- **Lista de permitidos por sesión en lugar de lista negra.** Cada login abre una
  sesión (`sid` en los tokens). Valkey guarda el jti vigente de cada sesión
  (`RT:{sub}:{sid}`) y un índice por usuario (`SESS:{sub}`). Un refresh solo se
  acepta con el jti vigente, de modo que perder o expulsar una clave obliga a
  volver a iniciar sesión pero nunca revalida un token revocado: el almacén falla
  cerrado. `JWT_MAX_SESSIONS_PER_USER` (1 por defecto) expulsa la sesión menos
  usada, y cambiar, resetear o fijar desde admin la contraseña cierra todas. AOF `everysec` se
  mantiene solo para que un reinicio no cierre todas las sesiones.
- **RabbitMQ 4** sustituye a SAQ mediante `aio-pika`. La configuración prioriza la
  estabilidad:
  - cola quorum durable con dead-letter a `<cola>.dlq`. El worker limita los
    reintentos (5, con backoff) porque en RabbitMQ 4.3 un `nack` con requeue no
    incrementa el contador de entregas; `x-delivery-limit` cubre los consumidores
    que mueren a mitad de un mensaje;
  - mensajes persistentes y publisher confirms;
  - ack manual tras el éxito y `prefetch` acotado;
  - conexión robusta y apagado ordenado del worker.
- El puerto `CommandEnqueuer` y `AsyncTaskResolver` no cambian; solo cambian el
  adapter y el proceso worker.

## Consecuencias

- La entrega es al-menos-una-vez: los handlers asíncronos deben ser idempotentes.
- Producción necesita un RabbitMQ y las variables `RABBITMQ_*`. Para los
  proyectos generados es una migración manual.
- CI, la preflight del template y los stacks locales levantan Valkey y RabbitMQ.
- Revisar la DLQ pasa a ser una tarea operativa: un mensaje allí es un trabajo
  que no se ejecutó.

## Context

`SaqCommandEnqueuer` implementa el puerto `CommandEnqueuer`; `config/tasks.py`
resuelve cada `MetaCommand` con `AsyncTaskResolver`. Valkey guarda además la
lista negra de refresh tokens y los contadores de rate limit.

## Decisions

1. **aio-pika directo**, no un framework de tareas: el contrato es un solo
   mensaje (`MetaCommand`) y así cada garantía queda explícita.
2. **Estabilidad en RabbitMQ:** exchange y cola durables, cola quorum con
   `x-delivery-limit`, dead-letter a `<cola>.dlq`, mensajes persistentes,
   publisher confirms, ack manual tras el éxito, `prefetch` acotado y
   `connect_robust`. Un payload inválido va directo a la DLQ. En RabbitMQ 4.3 un
   `nack` con requeue no incrementa `x-delivery-count` (solo `x-acquired-count`),
   así que el worker aplica el límite (5 intentos con backoff de 1 s a 30 s) y
   rechaza sin requeue el último; `x-delivery-limit` queda como red de seguridad
   para consumidores que mueren a mitad de un mensaje.
3. **Rendimiento en Valkey con fallo cerrado:** `io-threads`, lazyfree, sin
   snapshots RDB y `maxmemory-policy allkeys-lru`. La lista negra de refresh
   tokens se sustituye por una lista de permitidos por sesión (`RT:{sub}:{sid}`
   con el jti vigente e índice `SESS:{sub}`): perder una clave solo obliga a
   volver a iniciar sesión, nunca revalida un token revocado. AOF `everysec` se
   mantiene para que un reinicio no cierre todas las sesiones, no por seguridad.
   `JWT_MAX_SESSIONS_PER_USER` (1 por defecto) expulsa la sesión menos usada;
   cambiar o resetear la contraseña cierra todas.
4. El puerto `CommandEnqueuer` y `AsyncTaskResolver` no cambian: solo cambian el
   adapter y el proceso worker.

## Risks

- Entrega al-menos-una-vez: los handlers asíncronos deben ser idempotentes
  (ya lo exigía el reintento de SAQ).
- Producción necesita aprovisionar RabbitMQ; sin él, `run_async=True` falla al
  publicar en lugar de perder el trabajo en silencio.

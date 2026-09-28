## 1. Implementación

- [x] 1.1 AC-01/AC-02 Enqueuer RabbitMQ, topología quorum con DLQ y worker con ack manual; tests con broker real.
- [x] 1.2 AC-03 Configuración de Valkey y del pool del cliente.
- [x] 1.3 AC-04 Servicios en CI, preflight y compose.

- [x] 1.4 AC-05–AC-09 Lista de permitidos por sesión, límite N, revocación por contraseña y Valkey en allkeys-lru.

## 2. Integración y aceptación

- [ ] 2.1 AC-01–AC-09 Verificación integrada, CI remoto en verde y validación.

## Evidencia y aceptación

Responsable: agente integrador. Fecha: 2026-09-27. Rama `fix/ci-redis` sobre
`a0d4641`, cambios en stage sin commit.

| Criterio | Evidencia |
| --- | --- |
| AC-01/AC-02 | `tests/common/infrastructure/rabbitmq/test_rabbitmq_broker.py` con broker real (publish → ack, 5 entregas → DLQ, malformado → DLQ, no enrutable falla); `test_consumer.py`; `test_rabbitmq_command_enqueuer.py`. Stack dev: comando real reintentado 1–5 y dead-lettered; `stop worker` limpio |
| AC-03 | `valkey-cli CONFIG GET` en stack dev: `allkeys-lru`, `appendonly yes`, `io-threads 4`; clave persiste tras reinicio (AOF) |
| AC-04 | `just template preflight` con Postgres, Valkey y RabbitMQ exclusivos; servicios en `code_quality.yml` y `publish-template.yml`; RabbitMQ como usuario `rabbitmq` evita el `.erlang.cookie` de root (`eacces`) |
| AC-05–AC-09 | `test_jwt_token_service.py` y `test_redis_token_store.py` con Valkey real (rotación, N=1/N=2, logout, revoke-all, gracia, índice o clave perdidos → 401, sin `sid` → 401); `tests/api/test_password_revocation.py`, `test_refresh.py`, `test_logout.py`; `test_set_password.py` y `test_update_password.py` |

Comandos en verde: `just check`, `just backend code_quality`, `just verify`
(backend 311 unit, frontend 58 Vitest y build), `just backend test api` (29),
`just integration` (4), `openapi-check` (sin cambios), `check-migrations`,
`just docs typecheck` y `build`, `just template check`, `just agent-check`,
`actionlint`, `zizmor` sin hallazgos.

Pendiente: 2.1 hasta CI remoto en verde.

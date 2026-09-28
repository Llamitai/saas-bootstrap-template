## 1. Backend

- [x] 1.1 AC-02/AC-03 Tests rojos de durabilidad y anidamiento contra PostgreSQL; atomic_transaction anidable; commits en get_or_create y remove.
- [x] 1.2 AC-05 Migrar JOSE a joserfc con test de compatibilidad; validar iss de Google y cachear JWKS.
- [x] 1.3 AC-06 Rate limit y schema de registro; hashing con to_thread; Sentry sin PII.
- [x] 1.4 AC-07 Endpoints de salud con tests.
- [x] 1.5 AC-04 Envoltorios camelCase y operationIds; snapshot regenerado.

## 2. Frontend

- [x] 2.1 AC-01 E2E rojo de recarga y cambio de tenant; rotación en proxy; layout sin rotar.

## 3. Integración y aceptación

- [ ] 3.1 AC-01–AC-07 Verificación integrada y validación sobre la revisión final.

## Evidencia y aceptación

Responsable: agente integrador. Fecha: 2026-09-26. Base `7c7f3e1`, rama
`fix/stack-audit`, cambios en stage sin commit. Revisión probada: el índice
staged de esa fecha.

| Criterio | Evidencia |
| --- | --- |
| AC-01 | `tests/end-to-end/tenant-session.integration.spec.ts` (rojo antes del arreglo) y `tests/unit/proxy.test.ts`; `just integration`: 4 passed, repetido tras la revocación real, la ventana de gracia y `X-Client-IP` |
| AC-02/AC-03 | `tests/common/infrastructure/helpers/test_database.py`, `tests/users/infrastructure/repositories/test_sql_*.py` contra PostgreSQL |
| AC-04 | `test_openapi_contract.py`, `test_response_schemas.py`; `just backend openapi-check` exit 0; 45/45 operaciones con esquema 2xx |
| AC-05 | `test_jwt_token_builder.py` (token emitido por authlib sigue siendo válido), `test_google.py`, `test_jwt_token_service.py` con Redis real |
| AC-06 | `test_register__rate_limited_after_too_many_attempts`, `test_register_user__ignores_privilege_fields_and_returns_the_public_view`, `test_password.py`, `test_settings` |
| AC-07 | `tests/common/presentation/test_health.py`, `tests/api/test_health.py`; HEALTHCHECK de imagen apunta a `/api/py/health` |

Revisión independiente del diff: dos hallazgos (cierre de sesión ante fallos
transitorios; carrera proxy/route handler) corregidos con clasificación
`isSessionRejected`, ventana de gracia idempotente (`JWT_REFRESH_GRACE_SECONDS`) y
rate limit por `X-Client-IP` de confianza o por `sub` en refresh.

Comandos en verde: `just check`, `just verify` (backend 258 unit, frontend 58
Vitest y build), `just backend test api` (25), build local de ambas imágenes, `just backend check-migrations`,
`just docs typecheck` y `build`, `just template check`, `just agent-check`,
tests de `scripts/tests` (41), `actionlint`, `zizmor` sin hallazgos.

Pendiente: 3.1 queda abierta hasta confirmar la sesión única por usuario
(design, decisión 5) y ejecutar CI remoto.

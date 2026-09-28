## Context

Hallazgos verificados en `7c7f3e1`:

- `frontend/src/app/(protected)/layout.tsx` llama a `refreshBackendSession`
  desde un Server Component; el backend (`jwt_token_service.py`) pone en lista
  negra el jti guardado y la cookie del navegador queda revocada.
- `sql_email_address.py`, `sql_phone_number.py` y `SQLUserRepository.remove`
  hacen `flush` sin `commit`; `DatabaseConfig.get_session` cierra sin confirmar.
- `atomic_transaction` hace `commit()` incondicional; `SQLUserRepository`
  lo anida.

## Decisions

1. **Rotación solo donde se pueden escribir cookies.** `proxy.ts` refresca
   cuando falta o expira el access token de una navegación protegida, escribe
   ambas cookies en la respuesta y reenvía las nuevas en la request al render.
   El layout lee la sesión con `GET /v1/auth/session` usando el access token,
   sin rotar. El route handler `/api/auth/refresh` sigue siendo el camino del
   cliente.
2. **Transacción anidable.** `atomic_transaction` confirma solo si abrió la
   transacción; dentro de una ya abierta usa un savepoint
   (`session.begin_nested()`), de modo que un fallo externo revierte todo.
   Sin Unit of Work nuevo: la transacción sigue siendo por repositorio.
3. **`joserfc`** sustituye a `authlib.jose` con el mismo algoritmo y secreto,
   así que los tokens emitidos antes del cambio siguen siendo válidos.
4. **Contrato OpenAPI sin cambiar el wire.** Los endpoints siguen devolviendo
   `ApiJSONResponse`; `response_model`/`responses` con modelos genéricos
   `Envelope[T]` en camelCase solo documentan. Los requests usan alias camelCase.
   FastAPI no revalida cuando el endpoint devuelve un `Response`.
5. **Una sesión activa por usuario.** El código ya revocaba el refresh token
   anterior en cada login, pero el cliente Redis devolvía bytes y la clave de
   lista negra nunca coincidía, así que ni la rotación ni ese login revocaban
   nada. Al corregirlo se activa el diseño original: un login nuevo cierra la
   sesión anterior del mismo usuario. Pendiente de confirmación de producto.
6. **Enumeración en registro fuera de alcance**: decidirla exige verificación
   por email; se registra como deuda.

## Risks

- Proxy y layout cambian a la vez: un e2e de integración cubre login →
  recarga → cambio de tenant antes de dar la sesión por buena.
- Cambiar operationIds rompe clientes generados externos; no hay ninguno en el
  repositorio.

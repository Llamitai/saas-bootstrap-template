## Why

La auditoría del stack (2026-09-26) encontró defectos que los tests actuales no
detectan: el layout protegido rota el refresh token sin poder guardar el nuevo y
la sesión se pierde al recargar; hay escrituras que solo hacen `flush` y se
pierden; `atomic_transaction` confirma el bloque externo cuando se anida; JOSE
usa `authlib.jose`, que Authlib 1.8 elimina; el contrato OpenAPI no documenta
respuestas ni el camelCase real; y el acceso público tiene huecos (registro sin
límite, `iss` de Google sin validar, PII en Sentry, bcrypt en el event loop).
Consumidores: usuarios finales de la app, integradores que leen la referencia
API y quien opera los contenedores.

## What Changes

- La sesión del navegador sobrevive a recargas y cambios de tenant: solo el
  proxy o un route handler rotan tokens y siempre escriben la cookie nueva.
- Las escrituras de repositorio son durables y `atomic_transaction` es seguro
  al anidarse.
- JOSE migra a `joserfc`; Google ID token valida `iss` y cachea las claves.
- OpenAPI documenta cada respuesta 2xx con su envoltorio camelCase, sin
  parámetros espurios y con operationIds legibles.
- Registro con rate limit y sin campos ignorados; hashing fuera del event loop;
  Sentry sin PII por defecto.
- Endpoints de salud (`/api/py/health`, `/api/py/health/ready`) para
  contenedores.

## Capabilities

### New Capabilities

- `session-continuity`: continuidad de la sesión BFF ante recargas y rotación.
- `persistence-integrity`: durabilidad y atomicidad de escrituras.
- `api-contract`: contrato OpenAPI fiel al formato real.
- `public-surface-hardening`: registro, identidad externa, hashing, PII y salud.

### Modified Capabilities

Ninguna spec vigente cambia.

## Impact

Backend (auth, users, profile, common), frontend (proxy, layout protegido,
BFF), snapshot OpenAPI, Dockerfiles/compose (healthcheck) y documentación. Sin
cambios de schema ni de pantallas. La enumeración de emails en el registro se
mantiene y queda registrada: cerrarla exige un flujo de verificación por email.

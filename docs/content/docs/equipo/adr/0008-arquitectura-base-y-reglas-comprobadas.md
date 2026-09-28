---
title: "0008 — Arquitectura base del núcleo y reglas comprobadas por herramientas"
---

Estado: aceptado por la petición de auditar skills y constitución frente al stack
y aplicar todas las recomendaciones, 2026-09-26. Registra decisiones que el
código ya aplicaba sin ADR y añade las correcciones de la change
`harden-session-and-persistence`.

## Contexto y drivers

Los ADRs 0001–0007 tratan del proceso, los skills y la documentación. Las
decisiones de arquitectura del núcleo existían solo como reglas en `AGENTS.md`,
el perfil y los skills, sin su porqué. La auditoría encontró que esa ausencia ya
causaba defectos:

- El layout protegido rotaba el refresh token desde un Server Component, que no
  puede escribir cookies: la sesión se perdía al recargar.
- `atomic_transaction` confirmaba el bloque externo al anidarse, y había
  escrituras que solo hacían `flush`.
- El OpenAPI no documentaba respuestas ni el camelCase real.
- Un módulo backend nuevo quedaba fuera del contrato de capas sin que ningún
  check fallara.

Drivers: que un agente sepa por qué existe cada regla antes de "arreglarla", y
que cada regla crítica tenga un check que falle.

## Opciones

1. Mantener las reglas solo en prosa.
2. Registrar las decisiones en un ADR y respaldar cada regla crítica con un check
   determinista (linter, test de arquitectura o gate de CI).

## Decisión

Opción 2. Las decisiones del núcleo son:

- **Transacción por repositorio, no por request.** Cada escritura confirma dentro
  de `atomic_transaction`, que es seguro al anidarse (el bloque interno usa un
  savepoint y solo el externo confirma). Una escritura que solo hace `flush` es un
  bug. Dos repositorios distintos siguen sin ser atómicos entre sí; un Unit of
  Work necesitaría otro ADR.
- **camelCase en el borde de respuesta.** Los presenters trabajan con claves
  internas y la clase de respuesta convierte. El OpenAPI documenta el mismo
  formato con envoltorios genéricos y alias camelCase, sin cambiar el wire.
- **Tenancy por cabecera `X-Tenant`**, resuelta por dependencias del backend y
  añadida por los helpers HTTP del frontend.
- **BFF same-origin.** El navegador solo llama a `/api`; las credenciales de
  infraestructura viven en el servidor. Solo `proxy.ts` y los route handlers rotan
  tokens o escriben cookies; los Server Components leen la sesión sin rotarla.
- **Frontend por features** (`app -> features -> entities -> shared`) en lugar de
  las capas DDD globales retiradas.

Reglas y el check que las hace cumplir:

| Regla | Check |
| --- | --- |
| Capas backend y dependencias hacia dentro | `lint-imports`; un test exige que cada módulo de `backend/src` esté registrado en el contrato |
| Rutas con `add_api_route`, `commit()` solo en el helper, ORM solo en `common/database/models` | tests de arquitectura en `backend/tests/common/` |
| Capas, fachadas y `server-only` del frontend | `pnpm lint:boundaries` |
| Migraciones sin drift | `just backend check-migrations` en CI |
| Snapshot OpenAPI al día | `export_openapi.py --check` en CI |
| Imágenes construibles y workflows seguros | build de imágenes, actionlint y zizmor en CI |

## Consecuencias

- `AGENTS.md` enumera estos gates; un fallo en ellos es una regla del proyecto, no
  ruido.
- Crear un módulo backend exige registrarlo en `backend/pyproject.toml`.
- La enumeración de emails en el registro sigue abierta: cerrarla requiere un
  flujo de verificación por email y otro ADR.

---
title: "0006 — Auditoría de la guía de agentes y del catálogo externo de skills"
---

Estado: aceptado por la petición de auditar a fondo los skills y la constitución
del proyecto y aplicar las mejoras, 2026-09-26. Complementa los ADRs
[0003](0003-auditoria-y-depuracion-de-skills.md) y
[0005](0005-skills-con-invocacion-controlada-y-evals.md).

## Contexto y drivers

Cinco auditorías de solo lectura contrastaron la guía que reciben los agentes con
el código instalado y con la documentación oficial vigente (Claude Code, Codex,
OpenCode, FastAPI, Pydantic, SQLAlchemy, pytest-asyncio, Next.js 16, TanStack
Query v5, Docker, GitHub Actions). Las áreas auditadas fueron la constitución
(`AGENTS.md`, perfil, verificación y comandos), la guía backend, la guía frontend,
los skills operativos y los skills de terceros.

Los hallazgos principales fueron:

- La guía afirmaba contratos que el código no cumple: envelope con `datetime`,
  transacción por request, permisos activos, almacenamiento local cableado, una
  operación por archivo en frontend, validación zod de la configuración.
- Había ejemplos con símbolos o rutas inexistentes: tests de `python-testing`,
  scripts operativos con un módulo `projects`, la ruta BFF `/api/tenants` y
  estados de invitación que no existen.
- Había comandos que fallan tal como estaban escritos: argumentos de
  `infisical_seed.py` y `portainer_stack.py`, un `workflow_dispatch` inexistente,
  `uv lock` en la raíz y `docker scout --exit-code 1`.
- Había prácticas obsoletas o inseguras: Docker Content Trust ya retirado,
  acciones de CI fijadas por tag tras el compromiso de `trivy-action`
  (GHSA-69fq-xp46-6x23), y comandos que hacían push o PR sin petición.
- `frontend-architecture.md` tenía 1069 líneas; alrededor del 40 % repetía
  OpenSpec o `package.json` y mezclaba objetivo con estado actual.
- En los skills de terceros, cinco rutas ya no existen upstream y
  `next-best-practices` fue retirado por Vercel. Tres skills visuales competían
  con `impeccable`, y dos skills apuntaban a un árbol de ADR en el sitio público.

Los drivers son: que la guía describa el código real como contrato, que los
comandos citados se puedan ejecutar, y que no haya instrucciones obsoletas ni
catálogos duplicados.

## Opciones

1. Corregir solo los defectos de exactitud.
2. Corregir la exactitud, modernizar la guía y depurar el catálogo, sin cambiar
   el comportamiento del producto.
3. Además, corregir en el mismo cambio los defectos de producto encontrados.

## Decisión

Se adopta la opción 2.

- La guía describe el estado actual. Lo que es objetivo pasa a
  `architecture/frontend-roadmap.md`. La deuda se etiqueta como deuda y nunca se
  presenta como la regla a copiar.
- `AGENTS.md` añade comandos de arranque y tests focalizados, nombra los siete
  workflows, corrige la regla de transacciones y hace explícito que commit, push,
  PR, merge, release y deploy se hacen solo por petición.
- Los comandos de OpenCode dejan de crear issues, ramas, commits, pushes y PRs por
  su cuenta. `commit` deja de inyectar el diff completo y, en Claude Code, solo se
  ejecuta cuando la persona lo invoca.
- Por decisión de la persona usuaria se eliminan `design-an-interface`,
  `request-refactor-plan`, `decision-mapping`, `to-issues`, `to-prd`,
  `frontend-design`, `design-system-patterns`, `web-design-guidelines` y
  `next-best-practices`. En lugar de este último, `frontend-change` consulta la
  documentación que trae la versión instalada de Next
  (`node_modules/next/dist/docs`).
- `fastapi`, `impeccable`, `codebase-design`, `grilling`, `triage`,
  `domain-modeling` e `improve-codebase-architecture` se actualizan desde su
  upstream, con notas de proyecto mínimas; entre ellas, que los ADR viven en
  `docs/internal/adr/`.

Los defectos de producto descubiertos no se corrigen aquí: cada uno cambia
comportamiento y requiere su propio cambio OpenSpec con test de regresión.

## Consecuencias

Deuda de producto registrada, pendiente de cambios propios:

- **Frontend, caché entre sesiones:** el logout y el login no llaman a
  `queryClient.clear()`. Además, las query keys no incluyen el tenant ni el
  usuario, así que un cambio de sesión en la misma pestaña puede mostrar datos
  anteriores.
- **Frontend, envelope:** `auth-server.ts` y las rutas de login/refresh reenvían
  `datetime`, que llega vacío porque el backend envía `timestamp`.
- **Frontend, accesibilidad y tipografía:** `maximumScale: 1` bloquea el zoom
  (WCAG 1.4.4), y la tipografía Geist declarada en DESIGN.md no se carga.
- **Backend, clientes por request:** `build_async_domain` crea un cliente Redis y
  un `S3StorageService` en cada request, y el cliente Redis no se cierra.
- **Backend, bloqueo del event loop:** las subidas a S3 son síncronas dentro de
  código async.
- **Backend, excepciones:** `TenantRoleNotFoundError` está duplicado con estados
  HTTP distintos (404 y 409).
- **Backend, tests:** `asyncio_default_fixture_loop_scope` no está fijado, y los
  tests de base de datos comparten datos confirmados.
- **Repositorio, Dependabot:** no cubre el ecosistema `docker-compose`, y
  `node-lts.yml` fija acciones por tag.

Configuración local que decide la persona usuaria, sin aplicar:

- añadir `permissions.deny` para `.env` en `.claude/settings.json`;
- retirar del repo el hook `.claude/hooks/post-tool-call.py`, que solo se usa en
  local;
- fijar las versiones de los MCP con `npx …@latest` en `.mcp.json`;
- recortar permisos amplios de `settings.local.json`.

`release-template` mantiene los tags ligeros: sus tests los exigen de forma
deliberada.

## Verificación

Este cambio modifica guía, comandos, scripts de skills y el catálogo; no cambia el
comportamiento del producto. Los únicos archivos de código tocados son scripts de
skills y un comentario de test.

- `just agent-check` detectó 21 copias desfasadas y 9 copias huérfanas de skills
  eliminados. Las huérfanas se retiraron a mano, porque la sincronización nunca
  borra. Después de `just sync-skills`, ninguna copia pendiente.
- Suites: tooling 39 tests; `release-template` 21, `rename-project` 5 y
  `resolve-dependabot-prs` 62. Todas correctas.
- Scripts de `deploy-mvp`: `--help` correcto en todos. `infisical_seed.py` exige
  `--project-id` antes de cualquier llamada de red. No se ejecutó nada contra
  infraestructura real.
- `with_server.py`: smoke con servidor real, sin procesos huérfanos. Falla si el
  puerto ya está ocupado.
- `pnpm check:static` en frontend: tsc, Biome y fronteras de import correctos.
- `just template check`: 1694 archivos; round-trip idéntico y sin branding residual.
- Enlaces relativos de los 508 archivos modificados: todos resuelven salvo uno
  heredado del upstream de `impeccable`
  (`reference/degraded/asset-producer.md`).
- Smoke de clientes desde la raíz, `backend/` y `frontend/`:
  - Codex 0.157.0 lista 33 skills del proyecto, sin nombres repetidos, con los
    siete workflows y el nuevo `AGENTS.md` una sola vez.
  - OpenCode 1.17.11 ve los 40 skills canónicos sin repetir nombres.
  - Ningún skill eliminado aparece desde el repositorio.

No se volvieron a ejecutar los evals de activación, porque las descripciones de
los workflows no cambiaron. Las notas de proyecto de los skills externos se
pierden si se reinstalan con la CLI de skills; quedan listadas en `localOverrides`
de `skills-lock.json`.

---
title: "Verificación y aceptación"
description: "Recetas, selección por impacto, recursos exclusivos y evidencia de cierre."
icon: ShieldCheck
---

Ejecutar comandos desde la raíz Git. Requisitos: Docker Compose para suites
backend aisladas, Python/uv según el manifest, Node según engines y pnpm según
packageManager. Instalar con `uv sync --locked` en backend y
`pnpm install --frozen-lockfile` en raíz/frontend/docs por separado.

## Recetas y alcance

| Comando | Contrato |
| --- | --- |
| `just agent-check` | Metadata, enlaces operativos, configuración portable y sync sin reparación |
| `just sync-skills [nombres...]` | Repara solo copias del inventario; ejecutar después de editar `.claude/skills` |
| `just skill-evals [skills...]` | Evals de activación de `claude plugin eval` (llamadas facturadas); cada caso pasa si al menos 2 de 3 ejecuciones aciertan |
| `just backend quality` / `code_quality` | Corrección explícita: formato/autofix, tipos/imports |
| `just backend check` | Ruff format check + Ruff check + ty + import-linter, sin autofix; no arranca servicios dependientes |
| `just frontend check` | tsc + Biome check + boundaries, sin tests/build/autofix |
| `just check` | agent-check y checks estáticos de ambos stacks |
| `just backend test unit [args...]` | pytest excluyendo API; incluye integración PostgreSQL, no promete pruebas puras |
| `just backend test api` / `all` | Stack exclusivo, migración real, readiness con timeout, pytest y cleanup propio |
| `just frontend test [filtros...]` | Vitest run; selección vacía falla |
| `just frontend verify` | Check estático + Vitest + build |
| `just verify` | agent-check, backend check + tests no API, frontend verify; no implica API/E2E/migraciones/docs |
| `just frontend e2e` | Smoke Playwright, sin mocks de API ni login real; cero specs falla |
| `just integration [args...]` | Playwright con API real: error/login/cookies/logout mediante navegador → BFF → API |
| `just backend check-migrations [args...]` | Dos DB exclusivas: base y revisión previa → head, más Alembic check; falla ante grafo ambiguo/drift |
| `just change-status id` | Estado estructural OpenSpec y rutas del expediente |
| `just spec-check id [change\|spec]` | OpenSpec estricto, no interactivo; ID/tipo inválido falla |
| `just frontend new-feature name` | Crea fachada y carpetas; rechaza feature existente sin sobrescribir |
| `just docs typecheck` / `build` | Verificación del sitio documental |
| `just backend openapi` / `openapi-check` | Regenera o comprueba el snapshot `docs/openapi/openapi.json`; CI ejecuta el exportador con `--check` |

CI ejecuta el mismo `backend/scripts/check.py`, `pnpm verify` y selectores pytest.
El wrapper Docker de check ignora el entrypoint de espera a DB; no necesita red
de servicios. Las herramientas pueden crear cachés/builds; «sin mutación» significa
sin corregir fuentes. Revisar el diff final combinado después de verificar.

## Selección por impacto

Texto/mecánica: diff, enlaces y checks afectados. Skills/tooling: agent-check y
`python3 -m unittest discover -s scripts/tests -p 'test_*.py'`, más smoke de clientes.
Si cambia la descripción o el alcance de un skill con `evals/`, ejecutar
`just skill-evals <skill>` y registrar las tasas de activación.

Smoke de clientes: desde la raíz, `backend/` y `frontend/`, `codex debug prompt-input`
y `opencode debug skill` deben listar los siete workflows desde `.agents/skills`
o `.claude/skills`, sin nombres repetidos del proyecto. Registrar versión y
directorio. Un cliente ausente deja el smoke pendiente; la presencia de archivos
no lo sustituye.
Dominio/use case: check y regresión focalizada. Persistencia: PostgreSQL real,
rollback y migraciones. HTTP/authz: API real, éxito/error y scopes
permitidos/denegados; si cambia el contrato, snapshot OpenAPI regenerado y `just
backend openapi-check`. Frontend funcional: OpenSpec, frontend verify y recorrido
afectado. BFF/sesión/ contrato compartido: ambos stacks y `just integration`.
Caché: datos visibles tras mutación/cambio de scope. UI: teclado, foco, viewport y
estados; una captura aislada no prueba interacción. Docs renderizadas: tipos/build
y `just agent-check` (enlaces y frontmatter). Material distribuido del repo
canónico: `just template check` cuando exista el tooling Copier. Infraestructura
(Dockerfiles, compose, workflows): `docker buildx build` de cada imagen afectada,
`docker compose -f <archivo> config`, `actionlint` y `uvx zizmor .github/workflows`;
CI repite el build de imágenes y el lint de workflows en cada PR.

## Recursos exclusivos

[El runner](../../../../scripts/test_stack.py) crea un nombre Compose aleatorio por
invocación con [docker-compose.test.yml](../../../../backend/docker-compose.test.yml).
PostgreSQL/Valkey/RabbitMQ/SMTP, puertos API y filesystem temporal pertenecen al proyecto;
no monta `.env` del desarrollador. Usa un puerto Next libre, cookies y reportes por
E2E_RUN_ID; el navegador no reutiliza servidores. El runner cierra solo su proyecto
en finally, incluso ante fallo/interrupción. La suite actual no requiere worker
ni storage remoto; tests de esos efectos necesitan fixtures propias explícitas.
Los tests con marker `rabbitmq` usan el broker del stack (o de CI) mediante
`RABBITMQ_*` y declaran colas con nombres aleatorios que borran al terminar.

Las fixtures pytest crean una DB aleatoria y rechazan reutilizar una existente.
`TEST_DATABASE_NAME`, si se especifica, debe ser un identificador con `_test_` y
pertenecer exclusivamente a la ejecución. No apuntar tests mutantes al stack de
desarrollo. Un worktree solo aísla archivos; dos suites Next en el mismo checkout
se serializan porque comparten `.next`. Worktrees separados pueden usar E2E_PORT
y E2E_RUN_ID distintos. No ejecutar `just docker-prune-global` ni otro prune global como cleanup.

Para navegador: `pnpm -C frontend exec playwright install chromium` (en Linux,
`install --with-deps chromium`). E2E_PORT permite elegir puerto (3100 por defecto
en smoke); E2E_RUN_ID separa reportes. El gate de integración configura API y
selecciona explícitamente specs `*.integration.spec.ts`; no depende de credenciales
reales. Un browser ausente o una selección vacía falla, no se interpreta como éxito.

Migraciones: `--previous <revision>` elige la revisión soportada; por defecto usa
la anterior al head. `--fixture-sql <path> --assert-sql <path>` carga datos antes del
upgrade previo y exige un SELECT booleano verdadero después. Rutas son relativas
al backend dentro del contenedor. Esos fixtures deben cubrir la transformación real;
el checker no demuestra preservación semántica solo por no tener drift. No exige
un downgrade destructivo. `metadata.create_all` no sustituye Alembic.

## Evidencia y cierre

Un cambio funcional backend/frontend/fullstack usa una change OpenSpec con criterios
normativos y una sección «Evidencia y aceptación» en tasks.md. Cada criterio enlaza
resultado esperado, comando/entorno/exit code, observación, estado y reporte. Registrar
base, revisión probada, versión de definición, fecha y límites. Para trabajo sin
commit: `python3 scripts/source_snapshot.py --exclude <registro-de-evidencia>` genera
HEAD más digest de fuentes incluyendo archivos nuevos; documentar exclusiones.

Checks verdes y OpenSpec válido son verificación técnica. validate-change contrasta
el resultado con la necesidad, reutilizando evidencia vigente. Cambio de código,
contrato, fixture/config invalida evidencia afectada; justificar lo que sigue válido.
Un criterio obligatorio pendiente/fallido, entorno ausente o UAT requerida sin
resultado impide cierre. Corregir implementación o volver a definición según causa;
no ajustar criterios para ocultar fallos. Tasks completas/archive no equivalen a
aceptación ni a aprobación humana. Merge/release/deploy mantienen autorización propia.

Los skills OpenSpec y comandos opsx permanecen sin modificaciones. La orquestación,
CLI bloqueada y precondición de aceptación se aplican desde los siete workflows del
proyecto, antes de invocar sync/archive; no se corrige política editando contenido upstream.

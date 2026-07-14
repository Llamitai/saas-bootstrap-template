# Diseño del comando `frontend code_quality`

## Objetivo

Agregar un conjunto de recetas Just para que `just frontend code_quality`
formatee, aplique correcciones seguras de lint y valide tipos y límites de
importación del frontend. Las herramientas deben operar únicamente con
`frontend/` como directorio de trabajo.

## Alcance

La implementación funcional modifica solamente `just/frontend.just` y reutiliza
scripts que ya existen en `frontend/package.json`. No cambia el backend, el
`justfile` raíz, `frontend/package.json` ni la receta `frontend verify`.

Las correcciones automáticas quedan limitadas a archivos compatibles dentro de
`frontend/**`. No se habilitan correcciones inseguras de Biome.

## Interfaz

Se exponen estas recetas bajo el módulo `frontend`:

| Receta | Comando | Responsabilidad |
| --- | --- | --- |
| `format` | `pnpm format:write` | Formatear y escribir cambios en archivos del frontend. |
| `lint` | `pnpm lint:fix` | Validar lint y aplicar únicamente correcciones seguras de Biome. |
| `typecheck` | `pnpm type-check` | Validar TypeScript sin emitir archivos. |
| `lint-imports` | `pnpm lint:boundaries` | Validar los límites de importación feature-first. |
| `code_quality` | Dependencias anteriores, en ese orden | Ejecutar la puerta de calidad solicitada. |

La receta `lint` existente cambia de validación solamente a validación con
correcciones seguras. `pnpm lint:fix` no recibe `--unsafe`.

## Flujo y errores

Just ejecuta las dependencias declaradas por `code_quality`. Los pasos de formato
y lint pueden escribir cambios dentro de `frontend/**`; lint-imports es de solo
lectura. TypeScript no emite código, aunque su modo incremental puede actualizar
el caché ignorado `frontend/tsconfig.tsbuildinfo`. Si cualquier comando devuelve
un estado de error, Just devuelve error y no presenta la puerta como exitosa.

## Verificación

1. `just --list frontend` debe incluir `format`, `lint`, `typecheck`,
   `lint-imports` y `code_quality` entre las recetas del módulo.
2. `just --dry-run frontend code_quality` debe resolver los cuatro comandos en
   el orden format → lint → typecheck → lint-imports.
3. `just frontend code_quality` debe completar correctamente o reportar el
   fallo real de una validación.
4. El diff posterior debe confirmar que el comando no escribió fuera de
   `frontend/**`; el único cambio de configuración esperado es
   `just/frontend.just`.

## Why

El plan aprobado `docs/arch_plan.md` identifica gates incompletos y conocimiento
contradictorio entre clientes. Su implementación debe permitir definir, construir,
refinar, verificar y validar cambios del unirepo con evidencia reproducible.

## What Changes

- Siete workflows canónicos, mapa/perfil/verificación, inventario de distribución.
- Checks sin autofix, wrappers OpenSpec bloqueados y generador sin sobrescritura.
- Pruebas aisladas, gate Alembic, frontera browser/BFF/API y límites de imports.
- Paridad de CI distribuido y entrega ligada al commit validado.
- Revisión correctiva del drift encontrado por el nuevo gate de migraciones.

## Capabilities

### New Capabilities

- `agent-development-loop`: tooling y ciclo verificable del unirepo.
- `schema-model-parity`: migraciones reales coherentes con constraints del core.

### Modified Capabilities

Ninguna spec vigente cambia. La corrección de schema aplica la FK ya declarada por
el modelo y conserva índices únicos existentes.

## Impact

Instrucciones/skills, scripts/just, configuración CI/clientes, tests/backend/frontend,
Alembic y documentación interna. Sin nueva pantalla, proveedor, negocio ni deploy.

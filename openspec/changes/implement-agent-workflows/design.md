## Context

Se implementa el plan aprobado de configuración de agentes del unirepo. La baseline
estática backend/frontend pasa; el gate Alembic recién ejecutado detectó constraints
redundantes y una FK owner ausente en el esquema inicial.

## Goals / Non-Goals

Cerrar los mecanismos locales del plan con casos positivos/negativos, conocimiento
preservado y validación explícita. No introducir negocio, pantalla, proveedor,
publicación o refactor general del producto.

## Decisions

Conservar `.claude/skills` y ampliar el sync con inventario explícito. Checks y
correcciones se separan; local/CI comparten entrypoints. Las pruebas de servicios
usan Compose exclusivo, una imagen autocontenida sin `.env` y DB propias. OpenSpec raíz
se fija a 1.6.0; pnpm requiere su archivo de configuración para rechazar el
postinstall opcional, manteniendo frontend/docs independientes.

La paridad del schema se repara en una revisión nueva, sin editar la inicial:
constraints únicos redundantes se retiran conservando sus índices únicos y se
aplica la FK owner declarada en el ORM. Datos huérfanos producen un fallo explícito,
no una limpieza implícita. Ver [ADR](../../../docs/content/docs/equipo/adr/0001-ciclo-de-cambios-y-verificacion.md).

## Risks / Trade-offs

Checks de archivos no prueban discovery ni criterio semántico; registrar smoke de
clientes por versión/CWD y evaluaciones del ciclo aparte. Un pipeline local no
certifica ejecución/protección remota. Las suites Next comparten `.next` dentro de
un checkout y se serializan; worktrees usan puertos y reportes propios.

## Migration Plan

Distribuir fuentes/recetas antes de activar enlaces, sincronizar copias y comprobar
sin autofix. Aplicar Alembic sobre DB vacía y revisión inicial con usuarios/tenants
válidos; probar drift y errores. No modificar producción ni configuración remota.

## Open Questions

Disponibilidad real de proveedores/credenciales para smoke remoto: registrar límites
con evidencia sin inventar aprobaciones o aceptación de CI.

Restricción confirmada por el usuario: conservar intactos los skills OpenSpec y
comandos opsx. Las condiciones del ciclo viven en wrappers/workflows del proyecto.

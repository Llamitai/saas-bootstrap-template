---
title: "0001 — Ciclo de cambios, límites y verificación ejecutable"
---

Estado: aceptado para implementación por la petición de implementar el plan de
arquitectura, 2026-09-07. La aceptación operativa se registra en la change
`implement-agent-workflows`; esta decisión no afirma checks no ejecutados.

## Contexto y drivers

Instrucciones duplicadas, sync incompleto y gates divergentes impedían distinguir
estructura, pruebas y aceptación. Las fixtures create_all tampoco detectaban drift
en Alembic. Se necesita un kit portable que conserve auth/tenancy y ambos stacks.

## Opciones y decisión

Se conserva `.claude/skills` como fuente y el sync existente con inventario explícito,
frente a otro generador paralelo. Siete entradas coordinan expertise bajo demanda.
OpenSpec es el expediente único funcional, con aceptación por criterio/revisión;
texto y mecánica mantienen recorrido ligero. CLAUDE importa AGENTS, con MCP opcional.

Se separan autofix y checks, compartiendo entrypoints con CI. Compose de tests es
exclusivo, sin `.env` ni puertos/volúmenes ajenos; cada DB pertenece a una ejecución.
Import-linter amplía la protección entre módulos y frameworks; DomainContext sigue
componiendo puertos del producto y el adapter de serialización existente conserva
una excepción precisa `json_encoder -> fastapi`. No se relajan tipos ni contratos.

El gate Alembic detectó constraints únicos duplicados y la FK owner ausente. Se
agrega una revisión que retira solo constraints redundantes, mantiene índices únicos
y crea la FK `ON DELETE SET NULL` del ORM. La revisión inicial se conserva. Un owner
huérfano bloquea explícitamente el upgrade; no se modifica el dato para hacerlo pasar.

## Consecuencias

Nuevos tests deben distinguir mocks de integración y verificar errores deliberados.
El cierre requiere evidencia vigente además de checks verdes. Un cambio posterior
invalida resultados afectados. Las pruebas de clientes/proveedores remotos se
registran por versión y disponibilidad; un YAML no establece protección de rama.
Publicación, merge y despliegue conservan autorización y guards propios.

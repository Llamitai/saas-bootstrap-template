---
title: "0004 — Referencias de arquitectura backend ancladas al código instalado"
---

Estado: aceptado por la petición de reducir `clean-fastapi-ddd`, 2026-09-26.
Complementa [ADR 0002](0002-responsabilidad-del-skill-de-arquitectura-backend.md)
y reemplaza su decisión de conservar `references/scripts.md` como enlace.

## Contexto y drivers

`clean-fastapi-ddd` sumaba 2.580 líneas, unas 980 de ellas en bloques de código.
Once de sus catorce referencias ilustraban las reglas con un módulo `projects` que
no existe y citaban archivos inexistentes (`command_solver.py`,
`event_publisher.py`). Al contrastarlas con `backend/src` aparecieron afirmaciones
falsas que inducen defectos:

- los handlers de buses se ubicaban en `infrastructure/`, pero viven en `application/`;
- `Page.apply_presenter` se describía como mutación in situ, pero devuelve un `Page` nuevo;
- el envelope se describía con `datetime`, pero la respuesta emite `timestamp`;
- `DomainContext` incluía servicios inexistentes y un reintento de SAQ que el
  resolver no ejecuta, porque captura la excepción;
- `errors.md` prohibía `src/<módulo>/domain/exceptions.py`, que `auth`, `users` y
  `admin` usan, y afirmaba que `context` nunca llega al cliente.

Los drivers son: una sola fuente de verdad por convención, ejemplos del core
instalado según `AGENTS.md`, y referencias cortas que un agente pueda leer bajo
demanda sin arrastrar código que no pasa por tests, `ty` ni import-linter.

## Opciones

1. Corregir los ejemplos de `projects` manteniendo el código copiado.
2. Sustituir el código copiado por reglas breves y rutas a ejemplares instalados.
3. Eliminar las referencias y dejar solo el `SKILL.md`.

## Decisión

Se adopta la opción 2. Cada referencia enuncia reglas, errores comunes y una tabla
de rutas a ejemplares reales del core (`tenants`, `users`, `auth`, `common`). El
`SKILL.md` declara que, ante discrepancia, mandan el código y los contratos de
import-linter, y que la referencia se corrige en el mismo cambio.

Se eliminan `references/scripts.md` y `references/testing.md`, que solo
redirigían: el `SKILL.md` remite a `backend-change/references/operational-scripts.md`
y a `verify-change`/`python-testing`, e indica en una línea qué interfaz ejercita
cada capa. Se conserva el alcance acordado en el ADR 0002.

El perfil del proyecto corrige el envelope documentado a `{data, timestamp}`.

## Consecuencias

El skill baja a unas 755 líneas y toda ruta citada existe. Las convenciones que
el código aplica de forma no uniforme (nombre del diccionario de persistencia,
DTOs con `CamelCaseRequest` o `BaseModel`) se documentan como tales, sin exigir
renombrados fuera del cambio en curso.

Las referencias documentan el estado real aunque revele deuda: `check_tenant_permission`
no se aplica mientras `PERMISSIONS_ENABLED` sea `False`, los comandos diferidos no
se reintentan y el `event_bus` no tiene suscriptores. Corregir esa deuda requiere
cambios funcionales propios; este ADR solo modifica instrucciones y documentación.

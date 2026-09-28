---
title: "Decisiones de arquitectura"
description: "Convención e índice de los ADRs del proyecto."
icon: Scale
---

Las decisiones nuevas del boilerplate deben registrarse como ADRs cuando cambian
límites de módulos, contratos, persistencia, seguridad o flujos core.

## Convención

- Un archivo por decisión: `NNNN-titulo-en-kebab-case.md`, en esta carpeta.
- Idioma: español.
- Cabecera YAML con `title: "NNNN — Título"` en lugar de un `#` inicial: el sitio
  de documentación renderiza esta carpeta y toma el título de ahí. Añadir el ADR
  a este índice.
- Secciones mínimas: estado, contexto, drivers, opciones, decisión y consecuencias.
- Un ADR aceptado no se reescribe para cambiar la decisión; se agrega un ADR nuevo
  que lo reemplaza.

## Índice

- [0001 — Ciclo de cambios y verificación](0001-ciclo-de-cambios-y-verificacion.md).
- [0002 — Responsabilidad del skill de arquitectura backend](0002-responsabilidad-del-skill-de-arquitectura-backend.md).
- [0003 — Auditoría y depuración de skills propios](0003-auditoria-y-depuracion-de-skills.md). Su distribución a `.codex/skills` y `.opencode/skills` queda reemplazada por 0005.
- [0004 — Referencias de arquitectura backend ancladas al código instalado](0004-referencias-backend-ancladas-al-codigo.md).
- [0005 — Skills con invocación controlada, evals de activación y validación de especificación](0005-skills-con-invocacion-controlada-y-evals.md).
- [0006 — Auditoría de la guía de agentes y del catálogo externo de skills](0006-auditoria-de-guia-de-agentes-y-catalogo-externo.md).
- [0007 — Documentación unificada en Fumadocs con referencia OpenAPI generada](0007-documentacion-unificada-en-fumadocs.md).
- [0008 — Arquitectura base del núcleo y reglas comprobadas por herramientas](0008-arquitectura-base-y-reglas-comprobadas.md).
- [0009 — Valkey para caché y RabbitMQ para colas](0009-valkey-para-cache-y-rabbitmq-para-colas.md).

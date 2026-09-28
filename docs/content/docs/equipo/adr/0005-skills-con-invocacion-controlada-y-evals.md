---
title: "0005 — Skills con invocación controlada, evals de activación y validación de especificación"
---

Estado: aceptado por la petición de aplicar la auditoría de buenas prácticas de
skills, 2026-09-26. Complementa el [ADR 0003](0003-auditoria-y-depuracion-de-skills.md)
sin cambiar su catálogo ni sus responsabilidades.

## Contexto y drivers

La auditoría de septiembre de 2026 contrastó los 17 skills mantenidos con la
documentación de Claude Code (skills, *Skill authoring best practices*, evals de
plugins), la especificación abierta de agentskills.io, la documentación de skills
de Codex y la guía de OpenAI sobre evals de skills. Los hallazgos fueron:

- `release-template`, `resolve-dependabot-prs`, `deploy-mvp` y `rename-project`
  mutan repositorios remotos, infraestructura o todo el árbol, pero el modelo
  podía invocarlos por su cuenta. `resolve-dependabot-prs` declaraba además
  `allow_implicit_invocation: true` para Codex.
- Ningún skill tenía evals; la activación de los siete workflows, cuyas
  descripciones son deliberadamente vecinas, no estaba medida.
- Las descripciones de los workflows decían qué hacen, no cuándo usarlos. Los
  cuerpos eran párrafos compactos sin pasos, formato de salida ni errores comunes.
- `check_agent_config.py` solo exigía `name` y `description`.

Los drivers son: ninguna mutación externa sin petición explícita, activación
comprobable en lugar de supuesta, y reglas de formato aplicadas por una
herramienta y no por revisión manual.

## Opciones

1. Documentar las recomendaciones y dejar los skills como estaban.
2. Aplicar las recomendaciones solo en el texto de los skills.
3. Aplicarlas en el texto y respaldarlas con metadatos de invocación, evals
   ejecutables y comprobaciones estáticas.

## Decisión

Se adopta la opción 3:

- Los skills con efectos externos o masivos declaran `disable-model-invocation: true`
  y `policy.allow_implicit_invocation: false` en `agents/openai.yaml`. Solo se
  ejecutan cuando la persona los invoca (`/skill` o `$skill`).
- Los siete workflows describen «qué» y «Use when…», con los límites hacia el
  workflow vecino. Sus cuerpos usan pasos numerados, salida esperada y una sección
  *Gotchas* que reúne las advertencias ya existentes, sin añadir reglas nuevas.
- Cada workflow tiene `evals/` con dos casos que deben activarlo (inglés y
  español) y dos casos cercanos que pertenecen a otro workflow. Se ejecutan con
  `just skill-evals`, que aprueba un caso con al menos 2 de 3 ejecuciones
  correctas. `evals/` no se copia a otros clientes, porque solo Claude Code lo ejecuta.
- `agent-check` comprueba en los skills mantenidos: claves de frontmatter
  permitidas, descripción de hasta 1024 caracteres sin etiquetas XML, cuerpo de
  hasta 500 líneas, que cada referencia se nombre directamente desde `SKILL.md`,
  y que la invocación manual coincida entre Claude Code y Codex.
- Limpiezas asociadas: la plantilla de informe de `docker-hardening` y el rollback
  de `deploy-mvp` pasan a `references/`; `rename-project` deja de buscar nombres
  de productos ajenos y gana tests; `webapp-testing` retira los ejemplos Python
  que no son el gate E2E del proyecto; `tdd` y `python-testing` señalan sus
  fuentes de verdad en el código.

- Distribución a clientes: `.agents/skills` es la única copia versionada. El
  discovery real mostró que Codex 0.157.0 lee `.codex/skills` además de
  `.agents/skills`, por lo que `openspec-explore` y `openspec-propose` aparecían dos
  veces. También mostró que OpenCode 1.17.11 lee `.opencode/skills`, `.claude/skills`
  y `.agents/skills` y descarta nombres repetidos, así que `.opencode/skills` no
  aportaba nada. Se retiran `.codex/skills` y `.opencode/skills`; los 19 skills
  externos que solo estaban en `.codex` pasan a `.agents`. Se retiran también
  punteros duplicados de `AGENTS.md` o sin efecto: `instructions: ["AGENTS.md"]` en
  OpenCode (ya lo carga de forma nativa), `.codex/rules/project-rules.md` (Codex
  solo ejecuta archivos `.rules`), los README de ambos clientes (su procedimiento
  de smoke pasa a la guía de verificación), el hook JSON de OpenCode (OpenCode
  usa plugins) y el comando `brainstorm`, que repetía `define-change` con otro
  expediente `spec.md`. `agent-check` rechaza volver a crear esas raíces o esa
  instrucción.

Esto reemplaza la distribución `.codex/skills` y `.opencode/skills` del ADR 0003.
`tdd` y `webapp-testing` conservan su procedencia en `skills-lock.json` y la
disposición de archivos del origen; solo se ajusta su texto local.

## Consecuencias

Los cuatro skills con efectos externos ya no aparecen en el listado que ve el
modelo; hay que invocarlos por nombre. Un cambio de descripción o de alcance en un
workflow debe repetir sus evals. Esas ejecuciones consumen llamadas facturadas,
por lo que no forman parte de `just check` ni de CI.

Los evals se ejecutan cargando un solo skill. Miden si el skill se activa con
frases naturales y si se abstiene en peticiones vecinas; no miden la elección
entre dos skills cargados a la vez ni la calidad del resultado del workflow.

## Verificación

Esta auditoría cambia instrucciones, metadatos y tooling de skills; no cambia el
comportamiento del producto.

- `just agent-check` detectó 30 copias desactualizadas antes de sincronizar; después
  de `just sync-skills`, ninguna copia pendiente y ningún `evals/` distribuido.
- Tooling: 37 tests correctos en `scripts/tests`. Los cuatro tests nuevos del
  checker y el test de exclusión de `evals/` fallaban contra el código anterior.
- Tests de scripts de skills: `release-template` 21, `rename-project` 5 (nuevos) y
  `resolve-dependabot-prs` 62, todos correctos.
- `just template check`: 2114 archivos; round-trip idéntico, política Node LTS
  válida y render sin branding residual.
- Evals de activación con Claude Code 2.1.283, modelo por defecto, tres ejecuciones
  por caso y sin brazo de referencia: 28 casos y 84 de 84 ejecuciones correctas en
  los siete workflows (14 activaciones y 14 abstenciones, inglés y español). Coste:
  6,42 USD.

- Smoke de clientes desde la raíz, `backend/` y `frontend/`: Codex 0.157.0 lista 44
  skills del proyecto solo desde `.agents/skills`, ninguno repetido, sin los cuatro
  skills manuales y con `AGENTS.md` una vez. OpenCode 1.17.11 ve los 49 skills
  canónicos sin nombres repetidos. Las únicas repeticiones restantes en Codex
  (`skill-creator`, `find-skills`, `frontend-design`) vienen de carpetas personales
  del usuario, fuera del repositorio.

Los evals comprueban las descripciones actuales; no se midieron las anteriores,
así que no hay una comparación antes/después. El smoke de clientes lista skills,
no ejecuta una sesión interactiva.

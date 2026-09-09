# 0003 — Auditoría y depuración de skills propios

Estado: aceptado por la petición de auditar, corregir solapamientos y eliminar
skills innecesarios, 2026-09-08. Complementa los ADRs [0001](0001-ciclo-de-cambios-y-verificacion.md)
y [0002](0002-responsabilidad-del-skill-de-arquitectura-backend.md).

## Contexto y drivers

El catálogo contenía 51 skills canónicos. La auditoría revisa la interfaz de los
skills que mantiene el proyecto: descripción de activación, responsabilidad,
resultado, referencias y composición con los demás. Las copias de `.codex`,
`.opencode` y `.agents` son distribuciones de la misma fuente en `.claude`, no
responsabilidades independientes.

Se revisan 19 entradas: 17 locales o sin proveedor registrado que el proyecto
mantiene, y las adaptaciones locales de `tdd` y `webapp-testing`. Se conserva la
procedencia de estas dos últimas en `skills-lock.json`; una adaptación local no
convierte su origen en autoría propia.

Las otras 32 entradas quedan fuera de la depuración de contenido propio:

- 23 tienen proveedor en `skills-lock.json`: `codebase-design`, `decision-mapping`,
  `design-an-interface`, `design-system-patterns`, `domain-modeling`,
  `frontend-design`, `grill-me`, `grill-with-docs`, `grilling`, `impeccable`,
  `improve-codebase-architecture`, `mcp-integration`, `next-best-practices`,
  `request-refactor-plan`, `slash-command-factory`, `tailwind-design-system`,
  `to-issues`, `to-prd`, `triage`, `typescript-advanced-types`,
  `vercel-composition-patterns`, `vercel-react-best-practices` y
  `web-design-guidelines`.
- Los cinco `openspec-*` son generados y declaran proveedor OpenSpec.
- `fastapi`, `fastmcp-server`, `find-skills` y `playwright-cli` son bibliotecas
  generales conservadas; el lock no registra su procedencia completa. Su
  ausencia del lock no se interpreta como prueba de autoría propia.

Los alias externos `grill-me` y `grill-with-docs`, y la intersección entre las
bibliotecas visuales externas, no se presentan como duplicados propios resueltos.
Las instrucciones del proyecto y el workflow activo determinan cómo consultar
esas bibliotecas. OpenSpec y los comandos generados `opsx` conservan su contenido.

## Hallazgos y decisión

| Hallazgo | Acción y responsabilidad resultante |
| --- | --- |
| `brainstorming` repetía la definición, entrevista y paso a implementación de `define-change` | Eliminar el skill, su servidor visual, recursos y copias. `define-change` conserva la exploración de alternativas cuando hay decisiones pendientes y reutiliza el alcance aprobado. |
| `pytest-coverage` era otro bucle de generación/verificación e imponía 100 % a cualquier solicitud | Eliminarlo. `verify-change/references/python.md` concentra selección, reporte de líneas sin cubrir, tests significativos y objetivo limitado al alcance pedido. |
| `python-testing` se activaba por cualquier solicitud de testing y mantenía otro workflow de ejecución/formato | Acotarlo a sintaxis pytest, fixtures y ejemplos por capa. `verify-change` selecciona las comprobaciones; se mantienen `expects` y las excepciones async correctamente esperadas. |
| `tdd` se activaba por cualquier petición de tests de integración | Limitarlo al método incremental red/green/refactor dentro del workflow de implementación existente. |
| `webapp-testing` repetía recetas, preparación de servicios y aceptación | Mantener la técnica de inspección/interacción en navegador; la guía de verificación posee comandos y aislamiento, y `verify-change` recibe la evidencia. |
| `add-docs` atraía documentación interna/ADRs y exigía confirmar el idioma ya establecido | Limitarlo a páginas MDX del sitio Fumadocs, usar español por defecto y conservar las convenciones del sitio sin un segundo expediente de decisiones. |
| `docker-hardening` convertía un hallazgo concreto en auditoría global y una review podía escribir un informe | Respetar el alcance del hallazgo y el modo de review sin cambios. Aplicar las correcciones locales ya solicitadas, verificar resultados y mantener separada la autorización de cambios externos. |
| La referencia externa de `domain-modeling` propone otro directorio y formato ADR | Explicitar en el mapa raíz que prevalecen `docs/internal/adr/` y las secciones del índice local, conservando el contenido externo. |
| Codex exponía 12 skills propios dos veces al leer `.agents` y `.codex` | Distribuir los 17 skills mantenidos únicamente a `.agents` para Codex. Retirar sus copias de compatibilidad y comprobar que los nombres propios no se repiten. |

## Responsabilidades conservadas

El catálogo final contiene 49 skills; estos son los 17 mantenidos por el proyecto
que permanecen después de la depuración:

| Skill | Responsabilidad propia | Límite de composición |
| --- | --- | --- |
| `define-change` | Alcance, contratos, aceptación observable y preparación | Reutiliza definición; OpenSpec materializa los artefactos. |
| `backend-change` | Implementación y refinado backend, incluidos scripts operativos | Consulta arquitectura y tests; coordina persistencia con `schema-change`. |
| `frontend-change` | Implementación y refinado de interacción, estado y BFF | Sigue arquitectura feature-first y el diseño existente. |
| `schema-change` | Evolución de ORM, migraciones y datos | DTOs o validación zod no activan este workflow. |
| `verify-change` | Diagnóstico, selección/ejecución de checks, regresiones y cobertura solicitada | Produce evidencia técnica; no declara aceptación. |
| `review-change` | Hallazgos sobre un diff exacto | No edita ni aplica autofix. |
| `validate-change` | Comparación del resultado con los criterios acordados | Actualiza evidencia; devuelve defectos al implementador. |
| `clean-fastapi-ddd` | Propiedad de conceptos, dependencias, interfaces y composición backend | Biblioteca de arquitectura, no conductor de tareas ni manual pytest. |
| `python-testing` | Convenciones pytest, `expects`, fixtures, mocks y ubicación de tests | No selecciona gates ni impone objetivos de cobertura. |
| `tdd` | Técnica de implementación incremental mediante tests | No redefine alcance ni inicia otra aprobación. |
| `webapp-testing` | Inspección DOM, selectores, interacción, consola/red y evidencia visual | No crea otra suite de producto ni otro runner. |
| `add-docs` | Página ilustrada y renderizable del sitio Fumadocs | No posee ADRs, specs ni UI del producto. |
| `docker-hardening` | Evaluación y remediación de controles Docker solicitados | No despliega ni conduce mantenimiento de dependencias. |
| `deploy-mvp` | Primer aprovisionamiento y despliegue del producto generado | Conserva sus guardas; no publica la plantilla canónica. |
| `release-template` | Versionado y publicación de la plantilla canónica | Conserva sus guardas de repositorio, revisión y tag; no despliega un producto. |
| `rename-project` | Renombrado de una copia del boilerplate | Usa tokens y script existentes; no publica ni aprovisiona. |
| `resolve-dependabot-prs` | Resolución del conjunto solicitado de PRs Dependabot | Conserva sus guardas y evidencia de versiones; no sustituye una review genérica. |

Consultar una biblioteca desde un workflow es composición deliberada. Existe
colisión cuando dos entradas compiten por conducir el mismo resultado o
contradicen sus condiciones, no por compartir vocabulario. No se añade un skill
por cada referencia ni un nuevo router que repita esta tabla.

## Alternativas descartadas y consecuencias

Conservar aliases de los dos skills eliminados mantendría entradas redundantes
en discovery. Fusionar toda la arquitectura, los tests y la operación dentro de
los workflows haría perder interfaces útiles y volvería a ampliar sus
responsabilidades. Se mantienen las bibliotecas con contenido distinto.

Se actualiza `scripts/skill_inventory.json` y se retiran deliberadamente las
copias de los skills eliminados. La sincronización sigue rechazando contenido
huérfano; no se añade borrado automático. Los demás cambios se hacen en
`.claude/skills` y se distribuyen con `just sync-skills`.

El inventario registra los 17 nombres mantenidos en `project_skills`.
`agent-check` comprueba sus enlaces, presencia en `.agents` y ausencia de
duplicación con `.codex`. Los siete workflows se exigen en las raíces efectivas
del cliente, no en cada carpeta de compatibilidad. La distribución final es:

| Fuente/destino | Skills | Función |
| --- | --- | --- |
| `.claude/skills` | 49 | Fuente canónica, discovery de Claude. |
| `.agents/skills` | 31 | Los 17 mantenidos y el subconjunto externo existente; raíz nativa de Codex. |
| `.codex/skills` | 19 | Compatibilidad externa conservada; ningún skill propio duplicado. |
| `.opencode/skills` | 36 | Subconjunto de OpenCode, sincronizado con la fuente. |

La [documentación oficial de skills de Codex](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)
documenta la búsqueda en `.agents/skills` desde el directorio de trabajo hasta
la raíz y advierte que los nombres repetidos no se fusionan. La lectura real de
los clientes desde raíz, backend y frontend comprueba esta distribución. Las
copias externas de OpenSpec se conservan y quedan fuera de la garantía de
unicidad de los skills propios.

Por petición explícita adicional, también se retiran todas las copias de
`brainstorming` encontradas en los niveles personales y cachés de los clientes:
tres del proyecto y 21 de cachés de plugins. No había entrada activa en el lock
personal, el registro de plugins instalados ni directorios superiores. Esto es
estado local de esta ejecución, no una regla para borrar skills personales de
quien adopte la plantilla. No se modifica ningún marketplace remoto.

## Verificación

La auditoría cambia instrucciones, distribución y el control estático de su
inventario; no cambia el comportamiento del producto. No se generan tests de
implementación para texto.

- Metadata de los 17 skills mantenidos: válida con `quick_validate.py`.
- Enlaces de sus 150 documentos distribuidos: ningún destino local ausente.
- `just agent-check`: detectó las copias desactualizadas antes de sincronizar;
  después de `just sync-skills`, ninguna copia pendiente.
- Suite existente de tooling: 32 tests correctos.
- Cinco escenarios del contrato del checker en un directorio temporal, usando
  `expects`: distribución nativa válida, duplicación rechazada, ausencia nativa
  rechazada, recurso especializado roto detectado y nombre inválido rechazado.
- Los 27 archivos de skills OpenSpec y comandos `opsx` se mantienen idénticos
  a la línea base de esta auditoría.
- Búsqueda posterior en proyecto, directorios superiores y ubicaciones
  personales de clientes: ninguna carpeta de skill `brainstorming` restante.

- Evaluación independiente de nueve solicitudes: implementación definida,
  tests con `expects`, cobertura acotada, review Docker, corrección no-root,
  ADR interno, MDX de Fumadocs, recuperación en navegador y separación entre
  release/despliegue. Las contradicciones de idioma y defaults ADR detectadas
  se corrigieron y los dos casos se reevaluaron sin bloqueos.
- Discovery real con Codex CLI 0.153.4 (`debug prompt-input`) y OpenCode 1.17.11
  (`debug skill`), desde raíz, backend y frontend: 17/17 skills propios visibles,
  ningún nombre propio repetido y ninguno de los dos retirados presente.
  OpenCode se comprobó secuencialmente después de que dos procesos simultáneos
  disputaran el lock de su base local; ambos reintentos terminaron con exit 0.
- Copier sobre una copia temporal del árbol completo, incluidos archivos nuevos
  sin añadir nada al índice del usuario: 2128 archivos; round-trip idéntico,
  política Node LTS válida y render con otro nombre sin branding residual.
- `git diff --check`: sin errores.

Revisión base: `fdf70798187e402b1529a0f72fe51f578a7d4917`. Snapshot de fuentes:
`3636eef23dd4c43531118993af75194caca4876ee3053a4cb2bbac714216ba2c`, obtenido con
`scripts/source_snapshot.py` excluyendo este registro y
`openspec/changes/implement-agent-workflows/tasks.md` para evitar autorreferencia.
Los registros de evidencia se completan después de las comprobaciones; no
modifican las instrucciones ni el inventario comprobados.

La evidencia de discovery es del catálogo local de esos clientes, no una llamada
a sus proveedores. La evaluación independiente comprueba decisiones de selección;
no certifica que cualquier cliente o modelo elegirá siempre el mismo skill.

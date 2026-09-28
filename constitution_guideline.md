# Lineamientos para constituciones y skills

Investigación verificada el 2026-09-27. En este repositorio, una
**constitución** es un archivo `AGENTS.md` versionado que contiene instrucciones
persistentes del proyecto. Un **skill** es un archivo `SKILL.md` para una tarea
concreta, junto con sus archivos de apoyo opcionales. Esta guía se aplica a
Codex, Claude Code y OpenCode; no sustituye la configuración de esos clientes
ni las constituciones existentes del proyecto.

## Decidir dónde va una regla

| Pregunta | Ubicación | Motivo |
| --- | --- | --- |
| ¿El agente debe conocerla en casi cualquier tarea del repositorio? | `AGENTS.md` de la raíz | Se carga como contexto del proyecto. |
| ¿El agente debe conocerla siempre que trabaje en un área, sin importar el tipo de tarea? | `AGENTS.md` de esa área | La regla acompaña a los archivos que gobierna. |
| ¿Es un procedimiento repetible para una meta reconocible del usuario? | Un skill | Sus instrucciones completas se cargan cuando la meta es pertinente. |
| ¿Es una explicación extensa, una colección de ejemplos, una justificación arquitectónica o un dato del producto que puede cambiar? | Una guía, perfil, ADR o referencia del skill, enlazada desde las instrucciones | El agente consulta la fuente cuando la necesita y existe una sola copia autoritativa. |
| ¿La restricción debe cumplirse incluso si el agente pasa por alto el texto? | Código, pruebas, reglas de lint, permisos o CI | Las instrucciones orientan el comportamiento; no lo hacen cumplir por sí solas. |

Pregúntate: **¿Un cambio en los archivos gobernados sería incorrecto si el
agente nunca activara un skill?** Si la respuesta es sí, declara el invariante
en la constitución pertinente. Pon los pasos para cumplirlo en un skill solo
cuando formen un flujo recurrente. Si un flujo es obligatorio para cierta
clase de cambios, la constitución debe indicar cuándo se activa y remitir al
skill; el skill debe explicar el procedimiento. Esta regla de ubicación es una
recomendación del proyecto inferida de la distinción que hacen los clientes
entre instrucciones persistentes y skills cargados según la tarea
([AGENTS.md en Codex], [Memoria de Claude Code], [Skills de Claude Code],
[Reglas de OpenCode], [Skills de OpenCode]).

## Qué va en una constitución

1. **Alcance y orientación.** Indica qué archivos gobierna, el propósito del
   repositorio, los puntos de entrada pertinentes y dónde están los detalles
   autoritativos. Reserva el archivo raíz para reglas compartidas entre áreas.
   Coloca las particularidades de backend, frontend y docs en sus archivos
   anidados existentes.
2. **Invariantes y límites estables.** Registra las decisiones arquitectónicas
   propias del proyecto, límites de seguridad y datos, contratos públicos,
   convenciones de nombres o idioma, propiedad de archivos generados y límites
   sobre acciones irreversibles que rijan en el área. Di qué debe hacer o
   preservar el agente e incluye excepciones solo cuando cambien la decisión.
3. **Datos operativos para empezar a trabajar.** Indica las recetas de comandos
   canónicas, los requisitos pertinentes, los comandos destructivos excluidos
   y las verificaciones enfocadas del área. Enlaza una guía de verificación
   para la matriz completa. Si CI exige una verificación, identifica su fuente.
4. **Acceso a flujos y fuentes.** Indica cuándo usar un flujo del proyecto y
   dónde está su skill. Pide leer una fuente bajo una condición concreta (por
   ejemplo, la guía de esquema para una migración), en vez de exigir todos los
   documentos enlazados antes de cada edición.

Redacta reglas breves, directas y verificables. Coloca cada regla en la
constitución de menor alcance que corresponda y evita copiar el mismo párrafo
en la raíz y en archivos anidados. Enlaza la fuente de los datos en vez de
repetir versiones o detalles de implementación cambiantes. Usa títulos y
listas para facilitar la búsqueda. Revisa las reglas cuando cambien la
arquitectura o las herramientas y elimina las obsoletas. OpenAI recomienda
revisar periódicamente las instrucciones de `AGENTS.md`, que se cargan de forma
habitual, y evitar listas de lecturas obligatorias para toda edición. Claude
Code recomienda instrucciones concisas porque consumen contexto de la sesión
([Guía de OpenAI], [Memoria de Claude Code]).

No conviertas una constitución en un tutorial completo, una lista de tareas,
un cambio OpenSpec, un ADR ni una copia del manual de una herramienta. Aquí,
«mantener las peticiones del navegador en el mismo origen bajo `/api`» es una
regla de constitución; los pasos para implementar una ruta BFF pertenecen a
`frontend-change`. «Ejecutar la verificación de migraciones tras un cambio de
esquema» pertenece a la constitución del área; los pasos para crear y desplegar
la revisión pertenecen a `schema-change`.

## Qué va en un skill

1. **Una tarea reconocible y acotada.** Define la meta, la entrada esperada y
   la condición de activación específica en los campos YAML `name` y
   `description`. Explica qué hace el skill y cuándo usarlo. Excluye tareas
   cercanas solo si eso evita una selección equivocada. Mantén las
   descripciones lo bastante breves para distinguir los skills en un catálogo
   amplio.
2. **Procedimiento y decisiones.** En `SKILL.md`, indica la secuencia necesaria,
   las bifurcaciones, la evidencia que debe reunirse, el resultado esperado y
   cuándo preguntar o detenerse. Da comandos exactos si la operación es
   delicada; permite criterio cuando haya varias soluciones válidas.
3. **Material de apoyo según la necesidad.** Usa el archivo principal como una
   ruta breve hacia `references/` para detalles, `assets/` para plantillas y
   `scripts/` para operaciones deterministas. Indica cuándo consultar cada
   recurso. No obligues a cargar todas las referencias en cada ejecución.
4. **Verificación del propio skill.** Pruébalo con una petición directa, otra
   indirecta, una petición parecida que no deba activarlo, casos con datos
   faltantes y un caso límite representativo. Comprueba tanto su activación
   como la calidad del resultado en Codex, Claude Code y OpenCode si el skill
   es compartido.

Evita repetir los invariantes del repositorio en todos los skills. Remite al
`AGENTS.md` aplicable o al documento autoritativo y añade solo instrucciones
propias del flujo. Evita descripciones genéricas como «usar para trabajo de
backend» si el skill solo trata migraciones. Estas prácticas siguen las guías
oficiales sobre condiciones de activación precisas, divulgación progresiva y
pruebas de skills ([Guía de OpenAI], [Creación de skills de OpenAI],
[Creación de skills de Claude]).

## Carga de instrucciones en cada cliente

| Cliente | Constituciones | Skills | Comprobación práctica |
| --- | --- | --- | --- |
| Codex | Lee los `AGENTS.md` desde la raíz del repositorio hasta el directorio de trabajo; el archivo más cercano aparece después. La búsqueda se detiene en el directorio actual. | Descubre `.agents/skills/<name>/SKILL.md` del repositorio y carga su contenido al usarlo. | Inicia en el directorio previsto y pregunta qué archivos de instrucciones y skills están activos; lee expresamente la constitución de un área si trabajas por debajo del directorio inicial. |
| Claude Code | Las versiones actuales pueden leer `AGENTS.md` directamente si ningún `CLAUDE.md` o `CLAUDE.local.md` del proyecto tiene precedencia. Las instrucciones de la raíz y de áreas anidadas se cargan según los archivos a los que accede. El soporte directo requiere la versión 2.1.277 o posterior. | Descubre `.claude/skills/<name>/SKILL.md` del proyecto y carga el skill pertinente cuando hace falta. | Revisa `/context` y la lista de skills en una sesión nueva. Este repositorio no añade `CLAUDE.md`; comprueba la versión y la configuración del cliente. |
| OpenCode | Usa `AGENTS.md`; según su documentación, la búsqueda local toma el primer archivo coincidente al subir desde el directorio de trabajo. Por eso, un archivo anidado puede ocultar el de la raíz. Los enlaces de `AGENTS.md` no se importan automáticamente. | Descubre `.agents/skills` y `.claude/skills`; la herramienta `skill` carga el contenido seleccionado cuando hace falta. | Prueba desde la raíz y desde cada área. Si un archivo anidado oculta las reglas de la raíz, indica expresamente que el agente debe leerlas o configura instrucciones compartidas; evita copiar todo el archivo raíz. |

Estas son características de cada cliente, no una garantía universal de
precedencia. Comprueba qué instrucciones se cargan en cada cliente después de
cambiar la estructura de archivos. Usa identificadores únicos para los skills:
distintos clientes pueden seleccionar de forma diferente definiciones
duplicadas. Usa campos `name` y `description` compatibles entre clientes, con
un nombre que coincida con el directorio, y evita campos exclusivos de un
cliente en skills compartidos, salvo que sean opcionales deliberadamente
([AGENTS.md en Codex], [Skills de Codex], [Memoria de Claude Code],
[Skills de Claude Code], [Reglas de OpenCode], [Skills de OpenCode]).

## Aplicar la distribución de responsabilidades del repositorio

| Fuente existente | Responsabilidad |
| --- | --- |
| `AGENTS.md` de la raíz | Propósito del repositorio, contratos entre áreas, descubrimiento de comandos, condiciones de activación de flujos, política de origen y sincronización de skills, y prohibiciones generales. |
| `backend/AGENTS.md`, `frontend/AGENTS.md`, `docs/AGENTS.md` | Invariantes, puntos de entrada y verificaciones obligatorias propias de cada directorio. |
| `.claude/skills/<workflow>/SKILL.md` | Procedimiento de cada flujo y evidencia o resultado que debe producir. `.agents/skills/` es la copia generada y versionada. |
| Perfil del proyecto, guías de arquitectura, ADR, archivos de diseño y manifiestos | Datos actuales, fundamentos, ejemplos, versiones y contratos detallados. |
| Pruebas, reglas de importación, linters, verificaciones de compilación y CI | Garantías exigibles y evidencia objetiva. |

Cuando cambie una regla, edita su fuente responsable y actualiza los enlaces
breves que llevan a ella. Para cambios en skills de este repositorio, edita
`.claude/skills/`, ejecuta `just agent-check` para observar la diferencia
esperada, ejecuta `just sync-skills` y vuelve a ejecutar `just agent-check`;
conserva juntos los archivos fuente y sus copias generadas. No crees aquí
`.codex/skills/`, `.opencode/skills/` ni `CLAUDE.md`. Son decisiones de este
repositorio, no reglas universales de los clientes.

## Lista de revisión

- ¿Puede un colaborador identificar el alcance y la fuente responsable de cada
  regla?
- ¿La constitución indica **cuándo** importa un skill o una referencia sin
  incorporar todo su procedimiento?
- ¿La descripción del skill selecciona la tarea prevista y descarta otras
  cercanas?
- ¿Están los invariantes, los datos cambiantes, los procedimientos y las
  verificaciones automáticas en sus fuentes respectivas?
- ¿Se comprobaron los comandos, las rutas y las afirmaciones sobre la carga
  de instrucciones frente al repositorio y las versiones actuales?
- ¿Una sesión nueva en cada cliente compatible cargó la constitución prevista
  y descubrió los skills esperados?

## Fuentes

Los enlaces citados arriba corresponden a las guías oficiales de los clientes
y de creación de skills usadas en esta comparación.

[AGENTS.md en Codex]: https://learn.chatgpt.com/docs/agent-configuration/agents-md
[Skills de Codex]: https://learn.chatgpt.com/docs/build-skills
[Guía de OpenAI]: https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
[Creación de skills de OpenAI]: https://developers.openai.com/plugins/build/skills
[Memoria de Claude Code]: https://code.claude.com/docs/en/memory
[Skills de Claude Code]: https://code.claude.com/docs/en/skills
[Creación de skills de Claude]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
[Reglas de OpenCode]: https://opencode.ai/docs/rules/
[Skills de OpenCode]: https://opencode.ai/docs/skills

---
title: "0007 — Documentación unificada en Fumadocs con referencia OpenAPI generada"
---

Estado: aceptado por la petición de auditar `docs/`, reestructurarlo con Fumadocs
y aplicar las recomendaciones, 2026-09-26. Mueve a este sitio las rutas de
documentación citadas por los ADRs anteriores; sus decisiones no cambian.

## Contexto y drivers

La auditoría de `docs/` encontró:

- El sitio Fumadocs tenía cuatro páginas de una sola sección cada una, mientras el
  conocimiento vigente vivía fuera, en `docs/internal/`, sin renderizar ni
  buscable.
- Había planes ya implementados en el código: `docs/arch_plan.md`,
  `copier-impl.md`, el diseño de `release-template` y ocho specs en
  `docs/content/superpowers/`.
- La referencia de la API estaba escrita a mano (unas 580 líneas) y se
  desactualizaba sola, aunque FastAPI ya genera el esquema OpenAPI.
- El login del sitio era un guard de cliente: `llms-full.txt`, el Markdown por
  página y el índice de búsqueda se prerenderizaban sin protección.
- Cada página mezclaba tipos de contenido: glosario, arquitectura, operación y
  convenciones editoriales.

Los drivers son: una sola fuente, legible por agentes en el repositorio y por
personas en el sitio; una referencia de API que no pueda desfasarse del código; y
una organización por necesidad del lector.

## Opciones

1. Mantener `docs/internal/` aparte y ampliar solo el sitio.
2. Leer `docs/internal/` como segunda colección de Fumadocs, sin moverla.
3. Mover todo a `docs/content/docs/` con pestañas por necesidad (Diátaxis) y
   generar la referencia de la API desde OpenAPI.

## Decisión

Se adopta la opción 3, con estas elecciones de la persona usuaria:

- **Estructura.** Cinco carpetas raíz (`root: true`), mostradas como pestañas del
  layout Notebook: `(empezar)` (tutoriales; el grupo no añade segmento a la URL),
  `guias`, `conceptos`, `referencia` y `equipo`. Los contratos que leen los
  agentes (perfil, verificación, arquitectura frontend) y los ADRs pasan a
  `equipo/` y `conceptos/` como `.md` con frontmatter; los ADRs usan
  `title` en lugar de un `#` inicial.
- **Enlaces.** Las páginas enlazan con rutas relativas al archivo. Un plugin
  remark las convierte en URLs del sitio o en enlaces al remoto `origin`, y
  `agent-check` valida enlaces y `title` en todo el árbol.
- **OpenAPI.** `backend/scripts/export_openapi.py` exporta el esquema sin
  arrancar servicios a `docs/openapi/openapi.json`, que se versiona.
  `fumadocs-openapi` crea en memoria una página por operación en
  `referencia/api/<tag>/`. `just backend openapi` regenera el snapshot,
  `just backend openapi-check` lo comprueba y el job de backend en CI falla si
  está desfasado. El skill `openapi-sync` lleva ese flujo a los agentes y
  `backend-change` lo invoca tras cambiar el contrato HTTP.
- **Planes históricos.** Se borran los planes ya implementados. La change
  OpenSpec `implement-agent-workflows` se conserva, porque tiene tareas de
  aceptación externas pendientes.
- **Framework.** Se mantiene React Router, que Fumadocs soporta (también OpenAPI
  sin RSC), y se actualiza a Fumadocs 16.15 con ZBSearch.
- **Acceso.** Se retira el login de cliente. La privacidad, si hace falta, se
  resuelve en el hosting.
- **Estilo.** Layout Notebook con navegación superior, tipografía Geist, paleta
  de los tokens del producto en claro y oscuro, acciones de página (copiar
  Markdown, abrir en asistentes) y portada con `HomeLayout`.

## Consecuencias

- Las rutas `docs/internal/**` dejan de existir. `AGENTS.md`, los skills, los
  README y los tokens de la plantilla apuntan a `docs/content/docs/**`. El runbook
  de publicación sigue excluido de los proyectos generados, y ninguna página lo
  enlaza para no romper `agent-check` en ellos.
- Renombrar una ruta o un tag del backend cambia la URL de su página de
  referencia.
- Los endpoints no declaran `response_model`, así que la referencia generada
  muestra las respuestas sin esquema. Es deuda del backend, no del sitio.
- El exportador elimina los tags duplicados que produce declarar el mismo tag en
  `APIRouter` y en `include_router`. También añade el servidor local para el
  playground. El esquema servido en `/api/py/openapi.json` no cambia.

## Verificación

- `just docs typecheck` y `just docs build` correctos: 77 páginas HTML
  prerenderizadas, incluidas las 43 operaciones OpenAPI, más su Markdown para
  LLMs y el índice de búsqueda.
- Navegador sobre el build de producción: portada, guía, página OpenAPI, ERD
  Mermaid y búsqueda, en escritorio y a 390 px; modo oscuro revisado. Los enlaces
  a código apuntan a `github.com/<owner>/<repo>/blob/HEAD/...`.
- `export_openapi.py`: la salida en Docker y la local son idénticas. `--check`
  pasa con el snapshot y falla con uno alterado, y `just backend openapi` lo
  repara.
- `just agent-check` detectó 13 copias de skills desfasadas antes de
  `just sync-skills` y ninguna después. Tests de tooling: 40 correctos, incluido
  el nuevo de páginas sin `title` o con enlaces rotos.

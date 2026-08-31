# Resolución consolidada de PRs de Dependabot

## Contexto

El skill `resolve-dependabot-prs` procesa actualmente un PR por candidato. Ese
modelo repite preparación, validación, publicación y merge para cambios que
pueden revisarse con mayor claridad como una sola actualización estable. También
retrasa el cierre del inventario porque cada merge invalida la base de los PRs
restantes.

El nuevo flujo debe favorecer un único PR de reemplazo para las actualizaciones
estables y de bajo riesgo, revisar las notas oficiales de cada release, reparar
compatibilidad antes de validar y cerrar los PRs fuente únicamente después del
merge confirmado.

## Objetivo

Resolver en una sola operación el mayor conjunto seguro de PRs de Dependabot:

1. inventariar y clasificar todos los PRs abiertos;
2. consolidar los updates estables de bajo riesgo en un PR de reemplazo;
3. aplicar los cambios de código, configuración y lockfiles requeridos por sus
   release notes y breaking changes;
4. ejecutar una validación completa sobre el árbol consolidado;
5. publicar, revisar y fusionar el PR consolidado;
6. cerrar todos sus PRs fuente después de confirmar el merge.

## Criterio de elegibilidad

Un PR puede entrar al lote seguro cuando cumple todas estas condiciones:

- el parser obtiene dependencia, versión origen y versión destino sin errores;
- la versión destino es estable y no contiene marcadores prerelease;
- el impacto normativo es `patch` o `minor`;
- comparte repositorio y rama base con los demás miembros;
- existe evidencia oficial de registry, release o changelog para la dependencia;
- las notas no revelan un riesgo sin resolver;
- cualquier requisito de compatibilidad puede implementarse y verificarse en el
  mismo candidato.

Los updates `major`, no-SemVer, de impacto desconocido, prerelease o con
compatibilidad incierta no entran al lote autónomo. Se mantienen abiertos y
siguen el gate de aprobación existente. Un update estable que resulte riesgoso
durante la revisión se excluye del candidato sin bloquear el subconjunto seguro.

## Decisión de diseño

### Inventario y grupos

`inspect` seguirá produciendo el inventario completo. En vez de emitir solamente
grupos singleton, emitirá un grupo consolidable por rama base con todos los
PRs mecánicamente elegibles (`patch|minor`, estables y sin error de parser). Los
PRs no elegibles conservarán grupos singleton para que sus gates sean
independientes.

El SHA base del lote será el head actual de esa rama obtenido por `inspect`, no
el snapshot histórico de cada PR. La identidad del grupo se calculará con el
repositorio, la rama, ese SHA base y la lista ordenada `numero@headSha` de sus
fuentes. `manifestPaths` será la unión ordenada de sus manifests y
`observedAggregateImpact` el máximo normativo del grupo. Si la rama avanza, el
plan se invalida y se reinicia desde un inventario nuevo. Repositorios con varias
ramas base producen como máximo un PR consolidado por rama; nunca se mezclan
ramas de mantenimiento con la default branch.

La revalidación de cada fuente exigirá que su head SHA, repositorio base y nombre
de rama base sigan siendo exactos, pero no comparará el `pr.base.sha` histórico
con el snapshot del lote. El head actual de la rama se consultará y comparará una
sola vez con `candidate.base.sha` antes de cualquier mutación. Así se pueden
consolidar PRs antiguos de la misma ref sin tolerar que la rama avance después
del plan.

El candidato podrá seleccionar un subconjunto no vacío del grupo consolidable.
Esto permite expulsar una dependencia cuando sus notas o pruebas revelan riesgo.
El runner comprobará que todas las fuentes pertenecen al grupo, que están
ordenadas, que sus heads siguen vigentes y que manifests, versiones e impacto
son la proyección exacta del subconjunto. No se podrá incorporar un PR ajeno al
inventario.

La revalidación remota reconstruirá manifests, ecosistema y dependencias por
cada PR fuente. Nunca inferirá un ecosistema común desde la unión de manifests
del candidato. Si dos fuentes afectan al menos un mismo manifest y declaran la
misma dependencia canónica con destinos distintos, el runner rechazará esa
combinación. La misma dependencia podrá aparecer en manifests disjuntos.

### Preparación consolidada

Un candidato con más de una fuente usará siempre modo `replacement` y comenzará
desde el SHA base inventariado en un clon o worktree aislado. El agente:

1. obtiene release notes oficiales para cada dependencia;
2. registra evidencia por cada dependencia fuente, no una evidencia genérica;
3. aplica todas las versiones seleccionadas;
4. actualiza código o configuración según deprecations, cambios y breaking
   changes documentados;
5. agrega dependencias lockstep solo con evidencia oficial de compatibilidad;
6. regenera los lockfiles con el package manager del repositorio;
7. elimina del lote cualquier update que siga siendo incierto.

La evidencia se considera completa cuando cada identidad
`ecosystem:nombre-canonico@destino`, incluidas las dependencias lockstep
adicionales, tiene al menos una entrada cuyo `subject` coincide exactamente con
esa identidad. `summary` separará dos ejes mediante
`breaking=none|applicable|not-applicable; adaptation=not-required|<resumen>`.
Esto permite registrar una adaptación por un cambio no catalogado como breaking
y un breaking change documentado que no alcanza al proyecto. Un breaking change
aplicable requiere una adaptación concreta; una incompatibilidad sin adaptación
segura obliga a excluir la fuente.

El runner comprobará mecánicamente cobertura, identidad normalizada, forma del
resumen, formato SHA-256 del digest y clasificación. La selección de una URL
oficial, la correspondencia entre contenido y digest, la fidelidad del resumen y
la aplicación efectiva de las notas al código son responsabilidad de revisión
del agente. El contrato no afirmará que el runner descarga o interpreta el
contenido remoto ni que demuestra semánticamente el contenido del tree.

### Validación única

Después de terminar todos los cambios se ejecutará una sola matriz de validación
sobre el árbol final. La matriz será la unión de los comandos obligatorios para
las superficies afectadas por el lote. No se repetirá la suite completa por cada
dependencia.

El agente derivará esa matriz de `AGENTS.md`, instrucciones anidadas y CI. El
runner solo puede comprobar de forma mecánica que cada resultado declarado tuvo
exit code cero y corresponde al `treeSha`; no afirmará descubrir por sí mismo
todos los comandos requeridos. Los checks remotos del PR constituyen la puerta
final independiente y deben terminar antes del merge.

Si una prueba falla por un cambio documentado, se corregirá el código y se
repetirá la matriz sobre el nuevo tree SHA. Si el riesgo no puede resolverse con
confianza, se reconstruirá el candidato sin esa fuente y se validará el
subconjunto restante. Nunca se omitirán o debilitarán checks para conservar un
miembro del lote.

### Publicación, merge y cierre

El runner publicará un único PR de reemplazo. Su título describirá una
actualización consolidada y el cuerpo incluirá un marcador exacto por cada
`numero@headSha` fuente, el resumen de versiones, adaptaciones de compatibilidad
y comandos de validación.

El marcador de lote incluirá `sourceHash`, `planDigest` y `treeSha`. Si se corrige
un candidato ya publicado, el runner solo podrá reutilizar su rama y PR cuando
la identidad de repositorio, base y conjunto exacto de fuentes siga siendo la
misma; hará push fast-forward y actualizará idempotentemente el cuerpo al nuevo
marcador, head, evidencia y validaciones antes de continuar. Un PR con otra
identidad bloqueará la operación.

`finalize` esperará los checks remotos y las protecciones configuradas, verificará
el head exacto y fusionará el PR con el método permitido. Solo después de
confirmar el merge SHA comentará y cerrará cada PR fuente. La ejecución será
idempotente: podrá recuperarse después de una respuesta perdida sin duplicar PRs,
comentarios, merges o cierres.

Un reemplazo con múltiples fuentes no se enviará a una merge queue: el intervalo
entre encolar y fusionar permitiría que una fuente se cierre o fusione sin poder
cancelar atómicamente el reemplazo. En ese caso el PR consolidado permanecerá
abierto y el runner reportará la protección como blocker.

Si el merge consolidado no se confirma, todos los PRs fuente permanecerán
abiertos. El cierre de una fuente comprobará que el PR consolidado contiene su
marcador exacto y que el SHA fusionado coincide con el estado del plan.

El estado agregado `sources-closed` exigirá que todas las fuentes estén cerradas
con su marcador exacto. Tras una interrupción, el estado permanecerá `merged`
mientras existan fuentes abiertas y conservará el estado individual de cada una.
Un cierre concurrente sin marcador o un merge concurrente de una fuente será
ambiguo y detendrá los cierres restantes.

### Majors y casos inciertos

Los PRs excluidos conservan el comportamiento existente:

- prerelease: cierre únicamente con predicado mecánicamente revalidable;
- major, no-SemVer o desconocido: candidato preparado y validado, con aprobación
  explícita antes de mutaciones remotas;
- evidencia interpretativa o incompatibilidad no resuelta: PR abierto con
  blocker y siguiente acción exacta.

Un major nunca comparte plan ni token de aprobación con el lote estable.

## Cambios de contrato

Se mantendrá `schemaVersion: 1` porque el cambio relaja límites sin invalidar
objetos singleton existentes:

- `inventory-v1.Group.prNumbers` permitirá múltiples fuentes;
- `candidate-v1.sources` y `state-v1.sources` permitirán múltiples fuentes;
- los arrays de operaciones permitirán un `close-source` por cada fuente;
- modo `direct` seguirá exigiendo exactamente una fuente;
- modo `replacement` permitirá una o más;
- los validadores del runner recorrerán todas las fuentes y estados;
- la revalidación viva derivará metadata por fuente y rechazará destinos
  incompatibles sobre un mismo manifest;
- la evidencia cubrirá también dependencias adicionales y tendrá un resumen de
  breaking changes estructurado;
- el título y cuerpo del reemplazo reflejarán el lote completo.

Los candidatos singleton existentes seguirán siendo válidos, incluidos sus
`subject` y `summary` libres no vacíos. Los reemplazos singleton ya publicados
con el marcador v1 combinado se reconocerán por su fuente exacta y se migrarán
idempotentemente al cuerpo nuevo.

## Manejo de errores

- Un fallo de inventario, auth, paginación o parser no produce mutaciones.
- Un cambio en base SHA o head SHA invalida el plan completo antes de publicar.
- Un update riesgoso se excluye y se conserva abierto; no se cierra por
  inferencia.
- Un fallo de CI bloquea merge y cierres.
- Un cierre parcial recuperable conserva estado por fuente y reanuda únicamente
  las operaciones pendientes.
- Un PR fuente cerrado o fusionado concurrentemente genera ambigüedad y detiene
  el lote.

## Pruebas

La suite cubrirá como mínimo:

- agrupación determinista de varios patch/minor con la misma base;
- separación de major, prerelease, unknown, parser error y bases distintas;
- agrupación de PRs de la misma ref con `pr.base.sha` históricos distintos,
  seguida del rechazo sin mutaciones si avanza el head actual de la rama;
- selección segura de un subconjunto de un grupo consolidable;
- rechazo de fuentes, manifests, versiones o impactos que no correspondan;
- obligación de evidencia por cada dependencia destino, incluidas las
  adicionales, con identidad y resumen estructurados;
- evidencia para un breaking change no aplicable y para una adaptación requerida
  por un cambio no catalogado como breaking;
- revalidación viva de un lote mixto npm, uv y GitHub Actions;
- rechazo de destinos incompatibles para una dependencia en el mismo manifest y
  aceptación de la misma dependencia en manifests distintos;
- rechazo de modo `direct` con múltiples fuentes;
- plan de reemplazo con un cierre ordenado por cada fuente;
- estado multi-fuente y recuperación después de cierres parciales;
- creación de un único PR con todos los marcadores fuente;
- migración de un marcador combinado v1 para un reemplazo singleton;
- corrección fast-forward de un candidato publicado, actualización de cuerpo y
  recuperación ante respuesta perdida;
- rechazo de merge queue para reemplazos con múltiples fuentes;
- merge confirmado antes de cualquier cierre;
- cierre idempotente de todos los PRs involucrados;
- cierre concurrente sin marcador, merge concurrente de una fuente y reanudación
  después de cerrar solo la primera fuente;
- compatibilidad regresiva con candidatos singleton.

La verificación final incluirá la suite completa del runner, validación de los
JSON Schemas, `quick_validate.py` para el skill y el chequeo de sincronía de
`.claude`, `.codex`, `.opencode` y `.agents`.

## Criterios de aceptación

- Todos los updates estables y de bajo riesgo de una misma rama base pueden
  resolverse mediante un solo PR de reemplazo.
- Cada dependencia queda respaldada por release notes oficiales revisadas.
- Los cambios y breaking changes aplicables producen adaptaciones explícitas de
  código o configuración.
- La validación se ejecuta sobre el árbol consolidado final.
- Ningún PR fuente se cierra antes del merge confirmado.
- Los updates inciertos permanecen abiertos y no bloquean el lote seguro.
- Las copias distribuidas del skill quedan sincronizadas.

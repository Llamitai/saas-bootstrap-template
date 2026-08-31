# Parser seguro de cuerpos de PR de Dependabot

## Contexto

La skill `resolve-dependabot-prs` obtiene el nombre y las versiones de cada
dependencia desde el título y el cuerpo del PR. El parser actual busca frases
`bump ... from ... to ...` en todo el cuerpo. Los cuerpos generados por
Dependabot incluyen notas de release y listas de commits dentro de bloques
`<details>`; esas secciones pueden mencionar actualizaciones de dependencias
del proyecto upstream. El parser las interpreta como si fueran parte del PR y
eleva incorrectamente su impacto a `major` o `non-semver`.

Los PR agrupados presentan otro caso: el encabezado enumera varias
dependencias y cada transición aparece en una línea `Updates ... from ... to
...`. El parser no reconoce esas líneas y deja el inventario incompleto.

## Objetivo

Extraer únicamente las transiciones declaradas por Dependabot en el resumen de
nivel superior del cuerpo, tanto para PR individuales como agrupados, sin
aceptar menciones provenientes de changelogs o commits upstream.

La corrección debe:

- mantener el comportamiento autónomo y los gates existentes de la skill;
- clasificar correctamente todo el inventario abierto, incluidos los PR
  individuales y agrupados que originaron esta regresión;
- funcionar con futuros cuerpos estándar de Dependabot;
- continuar fallando de forma cerrada cuando no exista evidencia suficiente;
- mantener sincronizadas las copias de la skill derivadas de `.claude/skills/`.

## Fuera de alcance

- Inferir versiones desde diffs de manifests o lockfiles.
- Consultar APIs externas de registries.
- Cambiar las reglas de aprobación, validación, merge o cierre de PRs.
- Agregar excepciones por número de PR, dependencia o repositorio.

## Decisión

### 1. Aislar el resumen confiable

El parser incorporará una función pequeña que recorra el cuerpo por segmentos
y devuelva solamente contenido de nivel superior. Un contador de profundidad
ignorará todo lo comprendido entre etiquetas `<details>` y `</details>`. El
scanner reconocerá aperturas con atributos mediante `<details\b[^>]*>` y
cierres `</details\s*>`, de forma insensible a mayúsculas. Procesará todas las
etiquetas de una línea en orden, conservará únicamente los segmentos de texto
que estén a profundidad cero y tolerará bloques consecutivos o anidados. Cada
bloque eliminado se sustituirá por un salto de línea, incluso cuando su apertura
y cierre estén en la misma línea. Los segmentos de nivel superior nunca se
concatenarán directamente, lo que impide fabricar una transición a partir de
texto que no era contiguo. Así, el texto anterior a una apertura o posterior a
su cierre mantiene su nivel, pero permanece separado.

Las líneas fuera de esos bloques —incluido el banner temporal de rebase de
Dependabot— se conservarán. El banner no coincide con la gramática de
transiciones y por tanto no requiere una excepción propia.

El filtro devolverá tanto el texto confiable como un indicador de balance. Una
apertura sin cierre o un cierre sin apertura invalidará toda la evidencia del
cuerpo, aunque existan segmentos aparentemente válidos antes del error. En ese
caso el extractor podrá usar solamente el título como fallback; si el título
tampoco aporta una transición completa, el inventario producirá `PARSE`. El
parser no intentará recuperar texto ambiguo desde un cuerpo desbalanceado.

### 2. Reconocer dos formas explícitas

La extracción se realizará línea por línea y anclada al inicio de cada línea
del resumen confiable:

- `Bumps [nombre](url) from versión-origen to versión-destino`
- ``Updates `nombre` from versión-origen to versión-destino``

La primera cubre PR individuales. La segunda cubre cada miembro de un PR
agrupado. El encabezado narrativo de un grupo, que enumera dependencias pero no
incluye versiones, no se interpretará como una transición.

Los resultados se normalizarán con la limpieza de versiones ya existente y se
deduplicarán por identidad, versión origen y versión destino. La identidad se
obtendrá tras recortar espacios: en `uv` se aplicará la normalización PEP 503
(minúsculas y cada secuencia de `-`, `_` o `.` convertida en `-`); en los demás
ecosistemas se usará `casefold()` porque los nombres observados por npm, Docker
y GitHub son insensibles a mayúsculas. El nombre original recortado se
conservará en la salida. Una repetición exacta según esa identidad es
idempotente. Si una misma identidad declara más de un par de versiones
distinto, toda la extracción del cuerpo se considerará ambigua y se descartará;
el título solo podrá resolverla si expresa una única transición completa. Si el
cuerpo no produce ninguna transición válida, el título seguirá siendo el único
fallback.

La señal opcional `version-update:semver-*` se buscará únicamente en el resumen
confiable y en el nombre de la rama, no dentro de contenido upstream. Se
normalizarán todas las coincidencias y solo se conservará la señal si existe un
único valor distinto. Señales incompatibles se convierten en `None`, nunca se
resuelven eligiendo la primera. Además, una señal global solo se asociará a un
PR con una única dependencia; en PR agrupados cada transición se clasificará
por sus versiones explícitas y no heredará una señal global. Esto conserva el
fallo cerrado para referencias SHA de GitHub Actions agrupadas.

### 3. Conservar el fallo cerrado

No se cambia el contrato del inventario. Una dependencia sin versiones
verificables conservará impacto `unknown`; un PR que no pueda analizarse
seguirá reportando un error `PARSE` y quedará abierto. No se degradará un caso
incierto a patch o minor.

## Flujo de datos

1. GitHub entrega título, cuerpo, rama y archivos del PR.
2. El filtro separa la superficie confiable de los bloques `<details>` y marca
   cualquier estructura desbalanceada.
3. Los parsers anclados obtienen transiciones `Bumps` y `Updates` solo cuando
   la superficie es válida.
4. Si el cuerpo es inválido, vacío o no contiene transiciones, se intenta el
   título.
5. `classify_version` clasifica cada par sin cambios.
6. El inventario agrega el impacto y aplica los gates actuales.

Cada unidad conserva un límite claro: el filtro decide qué texto es confiable,
el extractor reconoce la gramática y el clasificador determina el impacto.

## Pruebas

Se añadirán pruebas unitarias que cubran:

- un PR individual cuyo bloque de commits contiene otro `bump` major;
- un PR agrupado con dos líneas `Updates` separadas por bloques `<details>`;
- bloques `<details>` con atributos, consecutivos y anidados, incluyendo varias
  etiquetas y segmentos de nivel superior en una misma línea;
- un bloque intercalado entre fragmentos que parecerían una transición al
  concatenarse, comprobando que el salto de línea evita evidencia artificial;
- una apertura sin cierre y un cierre sin apertura, comprobando que se descarta
  todo el cuerpo y solo se permite el fallback al título;
- el fallback al título cuando el cuerpo no contiene transiciones;
- la deduplicación de una transición repetida.
- dos pares contradictorios para el mismo nombre, comprobando que el cuerpo se
  descarta como ambiguo;
- nombres equivalentes por mayúsculas y, para `uv`, por normalización PEP 503;
- señales semver coincidentes, conflictivas y aplicadas a un PR agrupado.

Las pruebas del filtro de superficie confiable estarán separadas de las pruebas
de extracción para verificar directamente esa frontera. La verificación
incluirá la suite completa de la skill, el chequeo de sincronía
de skills y un inventario real de los PR abiertos. El resultado esperado es que
las transiciones reales determinen el impacto, que los grupos expongan todos sus
miembros y que ningún impacto proceda de notas de release upstream. Los números
de PR no forman parte del contrato porque Dependabot puede cerrar y regenerar
ramas mientras se ejecuta el trabajo.

## Integración y entrega

La implementación se hará únicamente en
`.claude/skills/resolve-dependabot-prs/`. Después se ejecutará
`just sync-skills` para regenerar las copias existentes en `.codex/`,
`.opencode/` y `.agents/`, seguido de `python3 scripts/sync_skills.py --check`.

La corrección se entregará en un PR independiente. Una vez fusionada, se
reinventariarán los PR de Dependabot y se retomará su preparación, validación y
resolución con el flujo normal de la skill.

## Criterios de aceptación

- Las menciones dentro de `<details>` nunca generan dependencias observadas.
- Los PR agrupados producen una dependencia por cada línea `Updates` válida.
- Los casos ambiguos continúan bloqueados en vez de clasificarse por defecto.
- Todas las pruebas y el chequeo de sincronía pasan.
- El inventario real queda completo y clasifica todos los PR abiertos según sus
  transiciones verdaderas.

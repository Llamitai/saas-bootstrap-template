# Diseño del skill `resolve-dependabot-prs`

## Objetivo

Crear un skill compartido por Claude Code, Codex y OpenCode que resuelva los
pull requests abiertos por Dependabot en el repositorio GitHub del proyecto
actual usando `gh`. El flujo prioriza versiones estables, verifica el código y
deja cada PR en uno de estos estados explícitos: fusionado, cerrado con evidencia,
esperando aprobación por ser `major` o bloqueado con una acción requerida.

Las actualizaciones estables `patch` y `minor` son autónomas. Una propuesta
estable `major`, de impacto desconocido o de impacto agregado `major` se prepara
y prueba localmente, pero requiere aprobación explícita antes de cualquier
mutación remota. Un PR fuera de política se cierra autónomamente solo cuando el
executor puede recomprobar el predicado; evidencia interpretativa exige una
aprobación explícita de cierre.

## Alcance y distribución

La fuente canónica es:

```text
.claude/skills/resolve-dependabot-prs/
  SKILL.md
  agents/openai.yaml
  schemas/
    inventory-v1.schema.json
    candidate-v1.schema.json
    plan-v1.schema.json
    state-v1.schema.json
  scripts/
    dependabot_prs.py
  tests/
    fake_cli.py
    test_dependabot_prs.py
    fixtures/
      *.json
```

`python3 scripts/sync_skills.py --all resolve-dependabot-prs` copia la fuente a
`.codex/skills/`, `.opencode/skills/` y `.agents/skills/`. Nunca se editan las
copias.

El skill opera únicamente sobre el repositorio asociado al remote `origin` del
proyecto actual. No actualiza dependencias sin un PR de Dependabot abierto,
salvo miembros adicionales de una familia lockstep necesarios para resolver uno
de esos PRs. No publica releases ni modifica otro repositorio.

## Componentes

### `SKILL.md`

Define el flujo, la política de estabilidad, la máquina de estados, las puertas
de aprobación y las verificaciones. Localiza `dependabot_prs.py` con respecto al
directorio del `SKILL.md` cargado, por lo que funciona desde cualquiera de los
cuatro packs.

### `scripts/dependabot_prs.py`

Es un ejecutor con biblioteca estándar de Python y tres subcomandos:

```text
dependabot_prs.py inspect --root <absolute-repo-root> [--now <RFC3339>]
dependabot_prs.py plan --inventory <json> --candidate <json> --output <json>
dependabot_prs.py apply --root <absolute-repo-root>
                        --candidate-root <absolute-candidate-root>
                        --plan <json> --state <json> --phase publish|finalize
                        [--parent-plan <approved-major-plan.json>]
                        [--approval-token <approve|reject|close>:<sha256>]
                        [--dry-run]
```

- `inspect` es de solo lectura y pagina todos los PRs abiertos.
- `plan` valida inventario y candidato, calcula identidad idempotente, orden de
  operaciones y token de aprobación. No usa red ni muta Git.
- `apply` es el único camino permitido para push, creación/reutilización de PR de
  reemplazo, merge y cierre. Revalida el estado remoto antes de cada operación.

Toda salida normal es un objeto JSON en stdout; diagnósticos van a stderr. La
opción `--now` permite pruebas deterministas y no participa en ningún digest.
`--dry-run` ejecuta las guardas y devuelve la lista de comandos sin mutarlos.

### Schemas

Los cuatro JSON Schema Draft 2020-12 son normativos, usan
`additionalProperties: false` en cada objeto y declaran todos los campos como
`required`; la nulabilidad solo existe donde se indica abajo. El script valida
los mismos invariantes sin depender de `jsonschema`.

### Tests

`test_dependabot_prs.py` importa el runner del script e inyecta `FakeRunner`.
`fake_cli.py` ofrece ejecutables `gh` y `git` falsos para pruebas de CLI, mantiene
estado remoto en fixtures y registra cada comando. Esto permite probar operaciones
destructivas sin red ni repositorios reales.

### `agents/openai.yaml`

Expone `display_name`, `short_description` y `default_prompt` para Codex. Las
otras superficies pueden ignorarlo.

## Interfaz `inspect`

### Selección inequívoca del repositorio

`--root` es obligatorio; no existe `--repo`. El script:

1. confirma que `--root` coincide con `git rev-parse --show-toplevel`;
2. exige un remote llamado `origin` con fetch y push URL que normalizan al mismo
   host y `owner/repo`;
3. exige que `gh repo view --repo <owner/repo>` coincida con ese valor;
4. valida `gh auth status` para ese host y obtiene el actor con `gh api user`;
5. pasa `--repo <owner/repo>` o el endpoint absoluto verificado a toda llamada
   `gh`; nunca confía en el contexto implícito de otro remote;
6. obtiene la default branch y sus SHAs desde GitHub, no desde el checkout local.

Los remotes adicionales se ignoran. Si falta `origin`, las dos URLs difieren,
el host no es soportado por `gh`, existe cualquier ambigüedad o el repo es un
fork cuyo `origin` no es el repositorio base de los PRs, termina sin mutaciones.

Cada PR aceptado debe tener como base el repo verificado y autor REST
`dependabot[bot]` de tipo `Bot`. `app/dependabot` se acepta solo como la
representación equivalente devuelta por `gh`. Los PRs se agrupan por base ref y
nunca se mezclan default y maintenance branches.

### Contrato `inventory-v1`

El objeto raíz contiene:

| Campo | Tipo |
| --- | --- |
| `schemaVersion` | entero constante `1` |
| `complete` | booleano |
| `generatedAt` | string RFC3339 UTC |
| `repository` | `Repository` o `null` en envelope fatal |
| `pullRequests` | array de `PullRequest`, ordenado por `number` |
| `overlaps` | array de `Overlap`, ordenado por `kind,key` |
| `groups` | array de `Group`, ordenado por `groupKey` |
| `errors` | array de `InventoryError`, ordenado por `code,prNumber` |

`Repository` contiene strings no nulos `host`, `nameWithOwner`, `remote`
(siempre `origin`), `root`, `defaultBranch`, `defaultBranchSha` y `actorLogin`.

`PullRequest` contiene:

| Campo | Tipo / enum |
| --- | --- |
| `number` | entero positivo |
| `url`, `title`, `body` | string |
| `author` | `{login: "dependabot[bot]", type: "Bot", sourceLogin: string}` |
| `base` | `{repo: string, ref: string, sha: SHA40}` |
| `head` | `{repo: string, ref: string, sha: SHA40}` |
| `maintainerCanModify` | booleano o `null` |
| `files`, `manifests`, `lockfiles` | arrays de paths POSIX únicos y ordenados |
| `dependencies` | array de `Dependency`, ordenado por `name,toVersion` |
| `observedAggregateImpact` | `patch|minor|major|non-semver|unknown` |
| `securityUpdate` | booleano |

`Dependency` contiene strings `name` y `ecosystem`
(`npm|uv|docker|github-actions|unknown`); `fromVersion`, `toVersion`,
`rawUpdateType` son string o `null`; `dependencyType` es
`direct|indirect|unknown`; `impact` usa el enum anterior; `prerelease` es
booleano o `null`.

`Overlap` contiene `kind` (`manifest|lockfile|dependency`), `key` string y
`prNumbers`, array ordenado de al menos dos enteros. `InventoryError` contiene
`code` (`ENV|AUTH|API|RATE_LIMIT|PARSE|REPO_MISMATCH|CONTRACT`), `message`
string, `prNumber` entero o `null`, y `transient` booleano.

`Group` contiene `groupKey` SHA-256 hex, una base `{repo,ref,sha}`, arrays no
vacíos y ordenados `prNumbers` y `manifestPaths`, y
`observedAggregateImpact`. En v1 cada Group es exactamente un PR: `prNumbers`
tiene un elemento, manifests e impacto se copian de ese PR, y `groupKey` es
SHA-256 de `v1\n<repo>\n<base.ref>@<base.sha>\n<number>@<head.sha>\n`.
`overlaps` no fusiona grupos: informa conflictos de serialización para obligar a
reinspeccionar después de cada merge o cierre. Así un major que comparte
`pnpm-lock.yaml` o `uv.lock` no retiene actualizaciones patch/minor distintas.

`complete: false` se usa cuando auth, paginación, API o identidad impiden saber
si se listaron todos los PRs; en ese caso no se permite `plan`. Si el fallo
ocurre antes de resolver repo/auth, el envelope fatal usa `repository: null`,
arrays vacíos y al menos un error; nunca inventa campos. Si el repo ya se
resolvió, puede conservar `repository` y resultados parciales, pero siguen sin
ser planificables. Un body
malformado conserva el PR, agrega error `PARSE`, usa impacto `unknown` y puede
mantener `complete: true` porque el conjunto de PRs sí está completo. Sin
embargo, `plan` rechaza cualquier source con error `PARSE`: ese PR queda
`blocked: transient` hasta que Dependabot regenere metadata válida o una futura
versión incorpore un parser verificable. Los `unknown` que heredan la puerta
major proceden de metadata válida con impacto no demostrable, no de un error de
parser.

El schema raíz usa `oneOf`: la variante fatal exige `complete: false`,
`repository: null`, los tres arrays de datos vacíos y `errors` no vacío; la
variante resuelta exige `repository` no nulo. La variante resuelta puede ser
incompleta, pero ninguna forma con `complete: false` entra a `plan`.

Los códigos de salida son `0` para inventario completo, `2` entorno/auth, `3`
consulta incompleta y `4` contrato o identidad inconsistente.

## Interfaz `plan`

### Contrato del candidato o decisión

El agente escribe un `candidate-v1`. El campo `decision` usa
`update|close-nonapplicable|close-declined-major` y el schema aplica `oneOf`:

- Para `update`, el agente prepara código y verificaciones en un clon o worktree
  aislado.
- Para cierre, no existe código candidato; se exige `closureReason`, evidencia
  permanente y, para una major rechazada, el digest de la propuesta rechazada.

Todos los candidatos contienen estos campos requeridos:

| Campo | Tipo |
| --- | --- |
| `schemaVersion` | entero constante `1` |
| `repository` | `Repository` del inventario |
| `base` | `{repo: string, ref: string, sha: SHA40}` |
| `groupKey` | SHA-256 hex de un `Group` del inventario |
| `sources` | array no vacío ordenado `{number: int, headSha: SHA40}` |
| `manifestPaths` | array POSIX no vacío, único y ordenado |
| `versions` | array no vacío ordenado `{name,ecosystem,from,to,impact,prerelease}` |
| `additionalDependencies` | array ordenado `{name,ecosystem,reason,evidenceUrl}`; puede estar vacío |
| `observedAggregateImpact` | impacto observado del Group, sin override |
| `effectiveImpact` | `patch|minor|major`; decisión conservadora final |
| `impactRationale` | string no vacío ligado a versiones parseadas y evidencia aplicable |
| `decision` | `update|close-nonapplicable|close-declined-major` |
| `closureReason` | enum de cierre o `null` |
| `parentPlanDigest` | SHA-256 hex o `null`; requerido para `close-declined-major` |
| `stabilityEvidence` | array de `ReleaseEvidence` |
| `closureEvidence` | array de `ClosureEvidence` |
| `mode` | `direct|replacement` o `null` |
| `targetPrNumber` | entero positivo para direct; `null` en los demás casos |
| `commitSha`, `treeSha` | SHA40 o `null` |
| `validation` | array de resultados de validación |

Una decisión `update` además exige `mode` (`direct|replacement`), commit SHA y
tree SHA exactos, y comandos de validación ordenados con `command`,
`exitCode: 0`, `treeSha` y `finishedAt`; `closureReason` es `null`. En modo
`direct` debe existir exactamente un source, `targetPrNumber` es ese número,
`commitSha` es su head SHA y `treeSha` es el árbol Git de ese commit. En modo
`replacement`, `targetPrNumber` es `null`. Una decisión de cierre
exige `mode`, commit y tree `null`, `validation: []` y `closureReason` del enum
`prerelease|withdrawn|duplicate-merged|already-in-base|unsupported-platform|superseded-merged|major-declined`.

Una actualización exige al menos un `ReleaseEvidence` con `kind`
(`registry|release|changelog|compatibility`), `subject`, `url`, `summary` y
`contentSha256`; `closureEvidence` queda vacío. Un cierre deja
`stabilityEvidence` vacío y exige exactamente un `ClosureEvidence` por source.
Cada entrada de `versions` usa los enums `ecosystem` e `impact` del inventario,
`from` string o `null`, `to` string no vacío y `prerelease` booleano o `null`.
Una dependencia adicional debe corresponder exactamente a una versión que no
procede de los PRs fuente; su impacto entra al máximo efectivo y nunca puede
rebajarlo.

`plan` no confía en los campos calculados por el agente: vuelve a derivar
`impact` y `prerelease` desde `ecosystem`, `from` y `to`, exige que las versiones
de los sources sean la proyección exacta del inventario y compara el resultado.
Una decisión `update` nunca admite `prerelease: true`; `prerelease: null` se
normaliza a impacto efectivo major y requiere la puerta correspondiente.

`ClosureEvidence` contiene `sourceNumber`, `predicate`
(`version-prerelease|replacement-merged|human-reviewed|user-decision`),
`subject` y `observed` strings, `url` string o `null`, y `contentSha256`
SHA-256 o `null`; además contiene los campos siempre presentes pero nulables
`replacementPrNumber` (entero positivo) y `replacementMergeSha` (SHA40).
`version-prerelease` se recomputa desde `toVersion`; `replacement-merged`
exige URL, PR number y merge SHA no nulos, y `apply` reconsulta exactamente ese
PR y SHA en el mismo repo. Los otros predicados exigen ambos campos replacement
nulos. `human-reviewed` exige URL y digest del contenido observado, pero no
autoriza cierre autónomo: requiere token
`close:<planDigest>`. `user-decision` solo vale para `major-declined`, usa URL y
digest nulos y se liga a `parentPlanDigest`.

La relación entre motivo y predicado es cerrada: `prerelease` exige
`version-prerelease`; `duplicate-merged|superseded-merged` exigen
`replacement-merged` cuyo PR fusionado contiene el marcador exacto del source;
`withdrawn|already-in-base|unsupported-platform` exigen `human-reviewed`; y
`major-declined` exige `user-decision`. Toda evidencia corresponde al mismo
`sourceNumber` de su entrada; no se comparte implícitamente entre sources.

`apply --candidate-root` señala el repositorio Git que contiene el commit. El
executor exige que su `origin` normalice al mismo repo del plan, que
`git cat-file -e <commit>^{commit}` exista y que
`git rev-parse <commit>^{tree}` coincida con `treeSha`, y que
`git merge-base --is-ancestor <base.sha> <commit>` sea verdadero. De ese repositorio sale
el push exacto; el commit no se reconstruye ni se transporta desde el worktree
principal. Para un cierre sin commit, `candidate-root` puede ser igual a
`--root` y solo se valida su identidad de origin.

`sources` debe coincidir exactamente con el PR singleton del `Group`. Paquetes
lockstep sin PR propio se declaran en `additionalDependencies` con evidencia
oficial de peer/compatibilidad y participan en `effectiveImpact`. `plan` rechaza
arrays vacíos, más de un source o dependencias adicionales sin evidencia. Si
otro PR abierto cubre un miembro lockstep, se procesa después sobre un inventario
nuevo o se propone su cierre con evidencia; no se incorpora silenciosamente.

### Identidad idempotente

Para todo plan, `plan` construye esta cadena UTF-8, con newline final:

```text
v1
<repository.nameWithOwner>
<base.ref>@<base.sha>
<manifestPath-1>
...
<sourceNumber-1>@<sourceHeadSha-1>
...
```

Paths y fuentes están ordenados. `sourceHash` son los primeros 12 hex del
SHA-256. `manifestSlug` usa el menor path: elimina `/` inicial, reemplaza cada
secuencia no alfanumérica por `-`, convierte a minúsculas, recorta guiones y a
32 caracteres; si queda vacío usa `root`. Solo el modo replacement usa la rama;
direct y cierres conservan `sourceHash` para identidad, pero
`destinationBranch` es `null`. La rama replacement es:

```text
automation/dependabot/<manifestSlug>-<sourceHash>
```

El marcador exacto es:

```html
<!-- resolve-dependabot-prs:v1 key=<sourceHash> source=<n@sha> -->
```

Si hay más de un PR con el marcador, se bloquea. Un único PR abierto se reutiliza
solo si su repo base, head branch, actor creador y source coinciden. Si su head
es el candidato exacto, se reutiliza sin push. Si su head es ancestro del nuevo
candidato, se permite únicamente un push fast-forward normal para corregir el
mismo grupo; el plan nuevo tiene otro digest y una major requiere aprobación
nueva. Heads divergentes bloquean: nunca se hace force-push. Un PR merged
significa que el reemplazo ya terminó. Uno cerrado sin merge se bloquea para no
reabrir ni duplicar silenciosamente en v1.

### Contrato `plan-v1`

El plan tiene exactamente estos campos raíz requeridos:

| Campo | Tipo |
| --- | --- |
| `schemaVersion` | entero constante `1` |
| `planDigest` | SHA-256 hex |
| `sourceHash` | 12 hex |
| `createdAt` | RFC3339 UTC |
| `candidate` | el objeto `candidate-v1` exacto validado |
| `destinationBranch` | string para replacement; `null` para direct o cierre |
| `operations` | array ordenado de `Operation` |
| `approval` | objeto `Approval` |

`Operation` contiene exactamente `{name,target}`. `name` usa el enum
`push|create-replacement|merge|close-source`; `target` es `branch:<name>`,
`replacement` o `source:<n@sha>` según corresponda. `Approval` contiene
`kind` (`none|update-major|close-reviewed|reject-major`), `required` booleano,
`approveToken`, `rejectToken`, `closeToken` y `parentPlanDigest`, los cuatro
string o `null`.

`plan` impone invariantes cruzados antes de escribir el archivo:

1. todos los sources existen en inventory con el mismo repo, base ref/base SHA
   y head SHA; nunca mezcla bases;
2. sources coinciden exactamente con el Group y manifests/versiones cubren sus
   dependencias y miembros lockstep adicionales;
3. `observedAggregateImpact` coincide con inventory; `effectiveImpact` se
   calcula por la tabla normativa sin overrides subjetivos;
4. todo resultado de validación declara el mismo `treeSha` candidato; las
   guardas contra los objetos Git se reservan a `apply`, que sí recibe
   `--candidate-root`;
5. `direct` exige un source y una operación `merge` dirigida a ese
   `source:<n@sha>`;
6. `replacement` exige destination branch determinista y, en orden, `push` a
   esa rama, `create-replacement`, `merge` del replacement y un `close-source`
   por cada source en orden numérico;
7. cualquier cierre exige exactamente un `close-source` por cada source en
   orden numérico, sin branch ni commit;
8. una combinación distinta es error de contrato, aunque cada campo aislado sea
   válido en el schema.

Para cierre no aplicable con predicado recomprobable, `operations` contiene solo
`close-source` y no requiere token. Evidencia `human-reviewed` exige
`close:<planDigest>`. Un plan de actualización major expone `approve:<planDigest>` y
`reject:<planDigest>`. Tras rechazo, `plan` genera una decisión
`close-declined-major` que conserva ese digest como `parentPlanDigest`, contiene
solo los `close-source` esperados y exige `reject:<parentPlanDigest>`.

La matriz de `approval` es cerrada: patch/minor y predicados autónomos usan
`kind: none`, `required: false` y todos los tokens nulos; una actualización
major usa `kind: update-major`, `required: true`, tokens approve/reject del
digest propio y `closeToken: null`; un cierre `human-reviewed` usa
`kind: close-reviewed` y solo `close:<planDigest>`; un cierre `major-declined`
usa `kind: reject-major`, solo `reject:<parentPlanDigest>` y declara ese parent.
Toda otra combinación es inválida.

Para calcular `planDigest`, `plan` serializa con JSON canónico (`sort_keys`,
separadores compactos, UTF-8) un objeto compuesto exactamente por
`schemaVersion`, `sourceHash`, `candidate`, `destinationBranch`, `operations` y
un objeto `approval` reducido a `kind`, `required` y `parentPlanDigest`. Excluye
`createdAt`, `planDigest` y los tres tokens derivados. Así quedan ligados repo,
base, fuentes, impactos, commit/tree, evidencias, parent, validaciones y
operaciones sin un ciclo de hash.

### Contrato `state-v1`

El plan es inmutable. `apply --state` crea o reanuda un archivo runtime y lo
escribe atómicamente mediante temporal + rename después de cada confirmación
remota. Todos sus campos son requeridos:

| Campo | Tipo |
| --- | --- |
| `schemaVersion` | entero constante `1` |
| `planDigest` | SHA-256 hex del plan inmutable |
| `repository` | `{host,nameWithOwner}` copiado del plan |
| `base` | `{ref,sha}` copiado del plan |
| `status` | `planned|published|waiting-checks|queued|merged|sources-closed|closed|blocked` |
| `replacement` | `{number:int,url:string,headSha:SHA40}` o `null` |
| `mergeCommitSha` | SHA40 o `null` |
| `operations` | array en orden del plan con `{name,target,status,attempts,lastObserved}` |
| `sources` | array `{number,headSha,status}`, status `open|merged|closed` |
| `blocked` | `{reason,action}` o `null` |
| `updatedAt` | RFC3339 UTC |

El status de operación es `pending|confirmed|blocked`; `attempts` es entero no
negativo y `lastObserved` string o `null`. Al reanudar, se recalcula el digest
del plan y digest, repo, base y sources deben coincidir con el estado. El objeto
completo se devuelve también por stdout en cada fase,
de modo que tests y agente observan exactamente el estado persistido. Un cierre
de plan termina `closed`; un merge direct termina `merged`; un reemplazo solo
termina `sources-closed`.

## Política de decisión

La clasificación usa SemVer para npm y refs `vN[.N.N]`; para `uv` usa el
release tuple de PEP 440, rellenado a tres componentes. Marcadores `a`, `b`,
`rc` y `dev` son prerelease; `.postN` es estable y se trata como patch; epochs,
local versions o formas que no permitan demostrar impacto quedan `unknown`.
Docker separa tag y digest. GitHub Actions separa major declarado y SHA. Un
update de seguridad conserva las mismas puertas; solo aumenta la prioridad del
reporte.

`observedAggregateImpact` conserva el dato bruto del inventario.
`effectiveImpact` nunca usa `unknown|non-semver`: `plan` lo calcula como
`patch|minor|major`. Todo `unknown|non-semver` se convierte a major; ni texto
libre ni evidencia interpretativa pueden rebajarlo en v1. `approval.required`
se deriva exclusivamente de `effectiveImpact == major` para actualizaciones.

Se aplica en este orden:

| Condición final | Decisión remota |
| --- | --- |
| Prerelease parseable o reemplazo/duplicado ya fusionado en el mismo repo | Cerrar autónomamente tras recomprobar el predicado, sin importar su major original. |
| Release retirada, cambio ya presente o incompatibilidad definitiva sustentados por `human-reviewed` | Proponer cierre y pedir aprobación `close:<planDigest>`. |
| Fallo de red/auth/rate limit/parser/fuente oficial no disponible | Dejar abierto y marcar `blocked`; nunca cerrar. |
| Estable SemVer patch o minor | Resolver y fusionar autónomamente. |
| Estable SemVer major | Preparar, validar y pedir aprobación antes de `apply`. |
| Docker con mismo tag y solo digest nuevo | Tratar como patch. |
| GitHub Action con SHA nuevo dentro del mismo major declarado | Tratar como patch. |
| No SemVer o impacto no demostrable | Tratar como major y pedir aprobación. |

El agregado observado usa la precedencia `unknown|non-semver > major > minor >
patch`; para el impacto efectivo los dos primeros se normalizan a major. La
pregunta major declara que aprobar continúa la actualización y
rechazar cerrará los PRs como major declinada. Una negativa inequívoca permite
generar el token `reject:<planDigest>` y cerrar; el comentario registra la
decisión sin atribuirla a incompatibilidad técnica. Sin respuesta permanece
abierta como `awaiting-major-approval`.

## Máquina de estados

```text
discovered -> classified
classified -> blocked
classified -> preparing -> validated
classified(nonapplicable) -> planned(close) -> closed-nonapplicable
validated -> planned(update)
planned(patch/minor) -> published -> waiting-checks -> merged
waiting-checks -> queued -> merged
merged(replacement) -> sources-closed
planned(major/uncertain) -> awaiting-major-approval
awaiting-major-approval -> approved -> published -> waiting-checks
awaiting-major-approval -> rejected -> planned(close-declined) -> closed-declined-major
planned|published|waiting-checks|queued -> blocked
```

Estados terminales de una ejecución: `sources-closed` (o `merged` para modo
directo), `closed-nonapplicable`, `closed-declined-major`,
`awaiting-major-approval` y `blocked`. `blocked` exige `reason` del enum
`transient|protection|unsafe-scope|stale-snapshot|ambiguous-remote|timeout` y una
acción requerida; no equivale a éxito.

## Puerta de aprobación major

Antes de preguntar, el agente muestra host/repo, base ref/SHA, PRs/head SHAs,
versiones, evidencia de estabilidad, breaking changes, commit/tree candidatos,
diff, validaciones, destination branch, operaciones y ambos resultados posibles:
`approve:<planDigest>` actualiza; `reject:<planDigest>` cierra como declinada.

Sin una respuesta inequívoca del snapshot exacto, no se invoca `apply`. Una
aprobación pasa `approve:<planDigest>`; un rechazo pasa
`reject:<planDigest>` a un plan de cierre derivado del mismo snapshot. `apply`
recalcula digest y verifica token, repo, base, fuentes, commit y tree. Para el
cierre declinado exige `--parent-plan`, recalcula también su digest y comprueba
que sea el plan update major original, con el mismo repo/base/sources, y que
`parentPlanDigest` y `reject:<parentPlanDigest>` coincidan. Cualquier diferencia
devuelve código `5` (`APPROVAL_REQUIRED`) o `6`
(`STALE_SNAPSHOT`) sin comandos mutantes y exige un nuevo plan y pregunta.

## Interfaz `apply` y orden de mutaciones

V1 procesa un plan a la vez, no usa concurrencia, force-push ni bypass
administrativo. El skill guarda cada `state-v1` en su workspace temporal con el
`planDigest` como nombre; nunca reutiliza un path de estado para otro digest.

Todo cierre escribe un marcador antes de confirmarse. Para un plan de cierre,
`evidenceDigest` es SHA-256 del JSON canónico del `ClosureEvidence` de ese
source; para el cierre posterior a un replacement es el `planDigest`. Los
formatos exactos son:

```html
<!-- resolve-dependabot-prs:v1 action=close source=<n@sha> reason=<enum> evidence=<evidenceDigest> -->
<!-- resolve-dependabot-prs:v1 action=close source=<n@sha> reason=superseded-merged evidence=<planDigest> replacement=<pr@mergeSha> -->
```

Un source abierto con el marcador exacto reintenta únicamente el cierre; uno
cerrado con el marcador cuenta como confirmado. Un source cerrado o merged sin
el marcador esperado, o con otro marcador, bloquea y nunca se reabre.

### Fase `publish`

- Para un plan de cierre no aplicable o major declinada, revalida sources y
  evidencia/token. Solo `version-prerelease` y `replacement-merged` permiten
  cierre autónomo; `human-reviewed` exige `close:<planDigest>` y
  `user-decision` exige el parent plan y token reject descritos arriba. Ejecuta
  `gh pr comment --body <marcador>` y luego `gh pr close` por source; termina
  sin crear rama ni PR.
- En modo directo, revalida el source PR y no hace push.
- En modo replacement, una rama ausente recibe el commit exacto con
  `git push origin <commit>:refs/heads/<branch>`. Una rama existente solo se
  acepta si apunta al candidato exacto, o si existe un único PR abierto con el
  marcador exacto, su actor es el actual y su head es ancestro del candidato;
  en este último caso hace push fast-forward normal. Cualquier otra rama o PR
  bloquea. Después crea o reutiliza el PR con el marcador exacto.
- Si se pierde la respuesta de red, consulta rama y marcador antes de reintentar;
  una coincidencia exacta cuenta como operación completada. Una rama exacta sin
  PR puede completar la creación solo cuando `state-v1` confirma el push del
  mismo plan; de otro modo se considera una colisión ambigua.
- Guarda estado `published`; nunca cierra sources en esta fase.

### Verificación remota

Justo antes de finalizar, `apply` consulta reglas con
`GET /repos/{owner}/{repo}/rules/branches/{base}` y, cuando existe protección
clásica, `GET /repos/{owner}/{repo}/branches/{base}/protection`. Normaliza la
unión de checks, approvals y merge queue requeridos. Un `403`, estructura
desconocida o contradicción entre reglas produce `blocked: protection`; no se
adivina. Un `404` autenticado significa «regla/protección ausente» solo para
estos endpoints documentados; cualquier otro `404` bloquea por identidad.

Después consulta el head actual, `reviewDecision` y todos los check runs del
head. La política es determinista:

- todo check requerido debe ser `success`; `neutral` o `skipped` requerido
  bloquea;
- todo check opcional debe ser `success|neutral|skipped`; cualquier otro estado
  final bloquea;
- `pending|queued|in_progress` se consulta cada 30 segundos hasta 30 minutos,
  informando progreso al menos una vez por minuto;
- `CHANGES_REQUESTED` bloquea; si las reglas exigen N approvals, se cuentan las
  últimas reviews `APPROVED` no dismissed de N actores únicos distintos del
  autor; una cantidad menor bloquea.

Un fallo de infraestructura puede reintentarse una vez antes de aplicar estas
reglas. Un fallo idéntico en la base se documenta pero no autoriza bypass.
Installs, builds y tests se ejecutan sin `GH_TOKEN`, `GITHUB_TOKEN`,
`SSH_AUTH_SOCK` ni credenciales cloud; si una dependencia privada las requiere,
el PR se bloquea y se pide autorización separada.

### Fase `finalize`

`apply` revalida plan, token, base/head SHAs, checks y reviews. Consulta
`mergeCommitAllowed`, `rebaseMergeAllowed` y `squashMergeAllowed`; sin merge
queue elige la primera permitida en orden `squash`, `rebase`, `merge` y ejecuta
`gh pr merge --<método> --match-head-commit <sha>`. Si las reglas normalizadas
exigen merge queue, ejecuta `gh pr merge --match-head-commit <sha>` sin forzar
método y espera hasta `merged`. Un error, método no permitido o timeout bloquea;
`queued` nunca es éxito.

Solo después de confirmar el merge commit cierra sources en orden numérico con
el segundo marcador. Un fallo entre el comentario y el cierre queda representado
en `state-v1` y la siguiente ejecución continúa la operación pendiente. Si un source
con el mismo head ya aparece cerrado sin merge, el replacement confirmado
permite añadir el marcador y contar el cierre; si aparece merged, se bloquea por
mutación concurrente.

En reintentos, operaciones ya reflejadas exactamente en GitHub se omiten. Un
estado múltiple, propietario inesperado o SHA distinto bloquea. Los códigos de
salida adicionales son `5` aprobación, `6` snapshot obsoleto, `7` protección o
checks y `8` bloqueo transitorio/ambiguo.

## Trabajo local y verificación

Leer `AGENTS.md` y reglas anidadas. Si el worktree tiene cambios, usar clon o
worktree temporal sin `stash`, `reset` ni restauraciones. Limpiar solo recursos
temporales creados por la ejecución que estén limpios; preservar y reportar
cualquier candidato no publicado.

Para este repositorio, según archivos afectados:

- backend: regenerar `uv.lock`, `just backend quality` y pruebas relevantes;
- frontend: regenerar lock y `pnpm -C frontend verify`;
- docs: regenerar lock, `pnpm -C docs types:check` y `pnpm -C docs build`;
- template/branding: `just template check`;
- skills: `python3 scripts/sync_skills.py --check`.

Una major usa la puerta completa de la superficie. Patch/minor pueden iterar con
checks enfocados, pero completan la puerta publicada antes del plan final.

## Inventario fijo acotado

La ejecución busca un punto fijo en máximo tres pasadas:

1. inventariar todos los PRs Dependabot abiertos;
2. resolver los números vistos en este orden: cierres autónomos verificables,
   security patch/minor, demás patch/minor y finalmente propuestas major;
3. repetir hasta que una pasada no descubra números nuevos.

El agente ejecuta un plan a la vez y vuelve a correr `inspect` después de cada
mutación remota. Si cambió base SHA, source head, manifests o estado, descarta
los planes todavía no aplicados y los regenera; los overlaps de lockfile o
manifest fuerzan esta reinspección, no una puerta major compartida.

Si la tercera pasada aún descubre PRs nuevos, estos quedan `blocked: timeout`
para la siguiente ejecución. El resultado cubre todos los números vistos; no
promete PRs creados después del timestamp final. Ningún estado `queued` o
`waiting-checks` es terminal.

## Validación del skill

Ejecutar:

```bash
python3 -m unittest discover \
  -s .claude/skills/resolve-dependabot-prs/tests -v
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  .claude/skills/resolve-dependabot-prs
python3 scripts/sync_skills.py --all resolve-dependabot-prs
python3 scripts/sync_skills.py --check resolve-dependabot-prs
```

El check byte-for-byte después de `--all` demuestra que los otros tres packs son
idénticos; `quick_validate.py` valida la fuente canónica.

Los tests con `FakeRunner` verifican al menos:

1. paginación, schema, orden y timestamp inyectado;
2. patch/minor autónomo;
3. major sin token y token incorrecto sin comandos mutantes;
4. major aprobada ligada al digest exacto;
5. prerelease cerrada antes de la clasificación major;
6. replacement-merged exige PR/merge SHA tipados y bloquea cualquier mismatch;
7. error transitorio sin cierre;
8. replacement: publish, merge confirmado y cierre posterior de sources;
9. reintento sin duplicar branch, PR, merge, comentario o cierre;
10. caída entre push/creación de PR o entre marcador/cierre, reanudada desde
   `state-v1`;
11. modo direct, candidate-root aislado, merge queue, reviews y checks
    opcionales/requeridos;
12. snapshot obsoleto y coincidencias múltiples bloqueados;
13. un patch/minor que comparte lockfile con un major conserva su plan autónomo
    y fuerza reinspección después de mutar.

## Criterios de aceptación

1. Schemas, runner y fixtures pasan sin red y no admiten campos ambiguos.
2. `inspect` pagina todos los PRs, verifica repo/autor y nunca muta.
3. La tabla de decisión cubre estable, prerelease, SemVer, non-SemVer, mixed y
   fallos transitorios sin contradicciones.
4. `planDigest` liga approval a repo, base, sources, candidato, validaciones y
   operaciones exactas.
5. `apply` impide toda major sin token válido y nunca cierra sources antes del
   merge confirmado.
6. V1 es secuencial, idempotente, sin force-push ni bypass administrativo.
7. Checks, reviews, queue, timeouts y snapshots obsoletos terminan en estados
   medibles.
8. `state-v1` permite reanudar cada fase y un cierre interrumpido sin duplicar
   mutaciones.
9. El punto fijo acotado asigna estado a cada PR visto.
10. Unit tests, validación rápida y sincronización byte-for-byte pasan.

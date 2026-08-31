# Política automatizada para la versión LTS de Node.js

## Contexto

El repositorio ejecuta actualmente Node.js 24 en `.nvmrc`, GitHub Actions,
GitLab CI y las tres etapas de `frontend/Dockerfile`. `frontend/package.json` y
`docs/package.json` usan `@types/node` 24, pero sus rangos de `engines` aceptan
cualquier major posterior; el `package.json` raíz ni siquiera declara el
engine y el `README.md` todavía indica erróneamente Node.js 22. Dependabot sólo
ignora la major 25 para los tipos y la imagen Docker. Esa excepción enumerada
permitió que el PR #109 propusiera `@types/node` 26 mientras Node.js 26 todavía
era una versión Current.

La política acordada no fija Node.js 24 para siempre: el proyecto debe usar la
major más alta que haya entrado oficialmente en LTS, pero nunca adelantarse a
una versión Current. El cambio entre majors debe llegar como un PR revisable y
nunca fusionarse automáticamente.

## Fuente de verdad externa

El estado de las líneas de Node.js se determinará con el calendario JSON del
Node.js Release Working Group:

`https://raw.githubusercontent.com/nodejs/Release/main/schedule.json`

Para una fecha UTC dada, una línea es elegible cuando:

- tiene una fecha `lts` válida y esa fecha ya llegó;
- su fecha `end` todavía no llegó, con el intervalo `lts <= hoy < end`;
- su clave tiene la forma `v<major>`.

La major objetivo será la más alta entre las líneas elegibles. No se inferirá
LTS por paridad ni por el hecho de que una versión exista en npm o Docker. El
calendario oficial está evolucionando y esas aproximaciones dejarían de ser
correctas.

El consumidor validará el código HTTP, el JSON y los campos requeridos antes de
tomar una decisión. Ante un error de red, un esquema desconocido o la ausencia
de una línea LTS soportada, fallará sin modificar ni publicar archivos. Si la
major oficial calculada es menor que `.nvmrc`, también fallará de forma visible:
ese estado puede significar que el repositorio usa Current/EOL o que el
calendario oficial cambió y nunca debe interpretarse como éxito.

## Contrato local de versión

`.nvmrc` será la fuente de verdad local y conservará una major explícita, por
ejemplo `24`. Un verificador sin acceso a red exigirá que esa misma major esté
representada en todos los consumidores:

- `package.json`, `frontend/package.json` y `docs/package.json` declararán un
  rango de engine cerrado a la major, `>=24.0.0 <25.0.0`;
- `frontend/package.json` y `docs/package.json` declararán `@types/node` como
  `^24`;
- el prerrequisito de Node.js en `README.md` indicará la misma major;
- todas las etapas de `frontend/Dockerfile` usarán `node:24-slim`;
- `.gitlab/ci/quality.gitlab-ci.yml` usará `node:24-slim` para el frontend;
- los pasos `actions/setup-node` propios del repositorio usarán `24`;
- Dependabot ignorará los saltos `semver-major` de `@types/node` en frontend y
  docs y de la imagen `node` en Docker.

Los rangos cerrados de `engines` evitan que una instalación local trate una
major Current como compatible. La regla genérica de Dependabot sustituirá las
listas como `25.x`: seguirá permitiendo parches y minors dentro de la major
vigente, pero impedirá cualquier salto major al margen del estado LTS.

El verificador distinguirá dos perfiles de repositorio:

- **Generado:** exige todos los consumidores comunes, incluido
  `.github/workflows/code_quality.yml`, y no exige maquinaria de publicación de
  la plantilla.
- **Canónico:** se detecta por la presencia de `scripts/build_template.py` y,
  además de los consumidores comunes, exige
  `.github/workflows/publish-template.yml` sincronizado.

En ambos perfiles, el verificador inspeccionará todas las referencias estáticas
a `actions/setup-node` de `.github/workflows/`: cualquier referencia adicional
que no use la major de `.nvmrc` será un error. La única referencia dinámica
permitida será `node-version-file: .nvmrc` dentro del workflow LTS. El updater
sólo modificará consumidores presentes y reconocidos para el perfil; no creará
archivos canónicos dentro de un proyecto generado.

## Herramienta de política

Se añadirá `scripts/node_lts_policy.py`, implementado sólo con la biblioteca
estándar de Python, con tres operaciones:

1. `check` valida que todos los pins locales coincidan con `.nvmrc`. No usa la
   red y será parte de CI.
2. `latest` descarga o lee desde archivo el calendario oficial, calcula la
   major LTS vigente y devuelve un objeto estructurado con `major` y
   `lts_date`. Cuando escriba en `GITHUB_OUTPUT`, ambos valores ya estarán
   validados respectivamente como entero decimal y fecha ISO `YYYY-MM-DD`.
3. `update <major>` actualiza de forma determinista los pins administrados. La
   operación exige primero que el repositorio satisfaga el contrato actual y
   aborta si falta un patrón esperado, para no hacer reemplazos parciales.

La herramienta no ejecutará `git`, no publicará ramas y no decidirá si una
major es LTS cuando se invoque `update`; esa separación permite probar las
transformaciones sin red. El workflow será responsable de llamar primero a
`latest` y pasar únicamente ese resultado a `update`. Ningún texto remoto no
validado se interpolará en comandos, nombres de rama o contenido publicado.

## Automatización de migración

Un workflow programado, también ejecutable manualmente, consultará el
calendario. Tendrá un grupo de concurrencia único y no cancelará una migración
en curso. Separará estrictamente preparación y publicación en dos jobs. Si la
major calculada coincide con `.nvmrc`, terminará sin cambios; si es menor,
fallará. Si es superior:

1. el job `prepare` con sólo `contents: read` ejecutará el actualizador sobre un
   checkout limpio del SHA de `main`;
2. configurará la nueva major de Node.js;
3. regenerará los lockfiles de frontend y docs con
   `pnpm install --lockfile-only --ignore-scripts` y la versión de pnpm fijada
   por el repositorio;
4. volverá a ejecutar el verificador local y sus pruebas, comprobará una
   allowlist exacta de archivos modificados y producirá un artifact con el
   patch, SHA base, major, fecha LTS y hash del patch;
5. el job `publish`, sin ejecutar pnpm ni código del repositorio, descargará y
   verificará ese artifact sobre el mismo SHA base;
6. publicará o actualizará una rama reservada
   `automation/node-<major>-lts`;
7. abrirá un PR titulado `chore(node): migrate to Node <major> LTS` si todavía
   no existe uno para esa rama;
8. disparará explícitamente `code_quality.yml` mediante `workflow_dispatch`
   sobre la rama publicada.

La allowlist común de una migración contendrá exclusivamente `.nvmrc`, los tres
`package.json`, los dos lockfiles pnpm, `README.md`, `frontend/Dockerfile`,
`.github/workflows/code_quality.yml` y
`.gitlab/ci/quality.gitlab-ci.yml`. El perfil canónico añadirá
`.github/workflows/publish-template.yml`; el generado no lo esperará. `update`
sólo realizará los reemplazos numéricos esperados dentro de esos archivos.
Cualquier archivo adicional, desaparición de un archivo requerido por el
perfil o cambio lateral provocado por pnpm abortará antes de crear el artifact.
El job de publicación repetirá la validación del SHA base, el hash y los paths
del patch antes de escribir.

El propio workflow LTS será la única excepción a los `node-version` numéricos:
después de ejecutar `update`, configurará Node con
`node-version-file: .nvmrc`. Así la misma ejecución puede regenerar los
lockfiles con la nueva major sin depender del YAML anterior. `check` aceptará
esa forma dinámica únicamente en este workflow y exigirá pins numéricos en los
demás.

El PR explicará la fecha LTS obtenida del calendario y pasará por los checks y
la revisión habituales. Los eventos `push` y `pull_request` producidos con
`GITHUB_TOKEN` no disparan por sí solos otros workflows; por eso la ejecución
explícita de `code_quality.yml` es parte obligatoria del flujo y el workflow
solicitará también `actions: write`. La ejecución despachada quedará asociada al
SHA de la rama y su resultado será visible antes de fusionar.

El workflow no usará auto-merge ni bypass de protecciones. Partirá siempre de
`origin/main` y publicará únicamente con `--force-with-lease` sobre la rama
reservada. Si la rama ya existe, antes de sobrescribirla verificará que exista
exactamente un PR abierto del bot, con esa rama como head y el título esperado;
cualquier rama sin PR, PR ajeno o estado ambiguo causará un fallo. Un grupo de
concurrencia impedirá dos escritores simultáneos.

Los dos checkouts usarán `persist-credentials: false`. El job `prepare` tendrá
únicamente `contents: read`, por lo que pnpm, las dependencias y las pruebas no
podrán obtener una credencial de escritura. Sólo el job `publish` tendrá
`contents: write`, `pull-requests: write` y `actions: write`; ese job no
ejecutará gestores de paquetes, lifecycle scripts ni código procedente del
repositorio. La credencial se inyectará explícitamente sólo en los pasos de
Git/`gh` que publiquen la rama, creen el PR y despachen los checks.

Si la configuración del repositorio impide que `GITHUB_TOKEN` cree PRs o
despache workflows, la ejecución fallará de manera visible sin cambiar `main`.
La ejecución manual seguirá permitiendo generar exactamente la misma migración
localmente.

## Proyectos generados por Copier

El script, sus pruebas, el verificador en CI y el workflow programado viajarán
intencionalmente a los proyectos generados. No dependerán de una GitHub App ni
de secretos exclusivos de `Llamitai/wise`: usarán sólo `GITHUB_TOKEN` con los
permisos mínimos declarados por job.

El `README.md` raíz, que sí viaja en la plantilla, indicará que el repositorio
generado debe permitir que GitHub Actions cree pull requests. No se dejará esta
instrucción sólo en `docs/internal/template-publishing.md`, porque ese runbook
es exclusivo del repositorio canónico. Si la política está deshabilitada, la
comprobación estática seguirá funcionando y el workflow programado fallará con
un diagnóstico accionable; nunca degradará a un token externo ni fusionará un
cambio. El dispatch explícito de `code_quality.yml` también forma parte de los
archivos generados, por lo que no requiere infraestructura propia del
repositorio canónico.

## Integración con Dependabot

Dependabot seguirá encargado de parches y minors dentro de la major vigente.
Los saltos major de Node y `@types/node` quedarán reservados al workflow LTS,
que es el único componente que consulta el estado oficial. Por tanto:

- el PR #109 permanece cerrado mientras Node.js 26 sea Current;
- cuando una major superior entre en LTS, no se reabrirá ese PR antiguo;
- se generará un PR nuevo con el runtime, los tipos, CI, imágenes, engines y
  lockfiles actualizados como una sola unidad coherente.

## Pruebas y verificación

Las pruebas de la herramienta cubrirán:

- selección de la major más alta antes y después de su fecha LTS;
- exclusión de líneas Current, terminadas o con esquema inválido;
- fallo cerrado ante datos vacíos o malformados;
- rechazo cuando la major local es superior a la LTS oficial;
- detección de divergencias entre `.nvmrc` y cada consumidor;
- detección del prerrequisito obsoleto en `README.md`;
- cobertura específica del pin de GitLab CI y de la única referencia dinámica
  permitida en el workflow LTS;
- validación de los perfiles canónico y generado sobre un render Copier real;
- rechazo de lifecycle scripts y de cualquier diff fuera de la allowlist de la
  migración;
- actualización completa en un repositorio temporal y rechazo de estados
  parciales inesperados.

CI ejecutará las pruebas unitarias y `scripts/node_lts_policy.py check` sin
red. La validación de implementación también incluirá los checks de frontend,
docs, el round-trip de la plantilla y la validación sintáctica de los
workflows. `scripts/build_template.py --check` ejecutará además el verificador
LTS dentro de un render Copier real para probar el perfil generado sin los
archivos canónicos excluidos. La consulta remota sólo ocurrirá en el workflow
programado o cuando se invoque explícitamente.

## Fuera de alcance

- No se fusionarán automáticamente migraciones major.
- No se seleccionarán versiones Current, nightly, release candidate o EOL.
- No se fijará una versión patch de Node.js; las imágenes y herramientas podrán
  recibir parches compatibles dentro de la major LTS.
- No se convertirá Dependabot en un detector de LTS ni se mantendrán listas
  manuales de majors no LTS.

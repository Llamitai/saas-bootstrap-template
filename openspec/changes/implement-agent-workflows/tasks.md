## 1. Contratos y distribución

- [x] 1.1 AC-01 Registrar baseline, inventario y sync con pruebas negativas.
- [x] 1.2 AC-04 Crear siete workflows y contrato de evidencia; revisar contradicciones auxiliares.
- [x] 1.3 AC-01/AC-05 Distribuir y comprobar recursos; discovery/activación en Codex y OpenCode desde raíz/backend/frontend.
- [ ] 1.4 AC-05 Completar smoke de Claude cuando su cuota permita una sesión nueva.

## 2. Tooling y fronteras

- [x] 2.1 AC-02 Separar checks, bloquear OpenSpec y proteger generador.
- [x] 2.2 AC-02 Probar wrappers, configuración y límites de imports con positivos/negativos.
- [x] 2.3 AC-03 Verificar stack exclusivo y recorrido real de sesión en navegador; incompatibilidad deliberada rechazada.
- [x] 2.4 AC-06 Corregir drift y probar upgrades/datos/errores reales.

## 3. Integración y aceptación

- [x] 3.1 AC-05 Alinear archivos CI, entrega por SHA, docs y round-trip Copier local.
- [x] 3.2 AC-04 Evaluar escenarios del ciclo, revisar diff integrado y registrar revisión/evidencia.
- [ ] 3.3 AC-05 Ejecutar pipelines en proveedores remotos y comprobar gates requeridos en la configuración de ramas.

## Evidencia y aceptación

Responsable: agente integrador. Fecha: 2026-09-08. Definición: proposal/design y
specs AC-01–AC-06 de esta change, incluidos en el snapshot. Base:
`752c5b71bcc3cee0da9872f8aad6e302e93c8b2f`. El plan del usuario ya estaba staged y
unstaged (AM); su índice se preservó. No se atribuye el resultado al HEAD limpio.

Snapshot de la entrega inicial de fuentes: **ba9677b34a91308a127c8ac89162c774bbb6b084839d95704a20a97db4211672**. Se calcula con
`python3 scripts/source_snapshot.py --exclude openspec/changes/implement-agent-workflows/tasks.md`.
Incluye archivos nuevos y el plan actualizado; excluye este registro para evitar
un hash autorreferencial. Reports/cachés ignorados por Git tampoco entran.

### Criterios

| Criterio normativo | Resultado esperado / observación | Verificación y evidencia | Estado |
| --- | --- | --- | --- |
| [AC-01](specs/agent-development-loop/spec.md) | Siete workflows y recursos en todos los destinos declarados; falta/drift/huérfano/escape falla sin reparación; sync explícito idempotente | `just agent-check` exit 0; tests sync/config dentro de 32 tests de tooling. Las nuevas copias OpenSpec son idénticas; fuentes upstream y comandos opsx no tienen diff | Satisfecho |
| [AC-02](specs/agent-development-loop/spec.md) | Checks sin autofix, CLI OpenSpec local bloqueada, selección inválida rechazada, generador conserva código existente | `just verify` exit 0; wrappers válidos/ausentes/inválidos, imports AST y selección E2E vacía cubiertos por tooling; locks congelados y spec-check exit 0 | Satisfecho |
| [AC-03](specs/agent-development-loop/spec.md) | Browser envía login inválido/válido al BFF y API real, ve recuperación, recibe cookies HttpOnly y cierra sesión con Enter en viewport 390×844 | `just integration` exit 0, 2 specs Chromium; contrato BFF temporal `emailAddress: null` hizo fallar la aserción esperada (exit 1), fuente restaurada y gate final verde; solo proyectos Compose propios eliminados | Satisfecho |
| [AC-04](specs/agent-development-loop/spec.md) | Un verde técnico contradictorio o evidencia antigua no permite cerrar; definición precisa se reutiliza, docs ligeras no crean specs | Codex/OpenCode activaron validate-change y leyeron evidence.md; rechazaron cierre. Evaluador independiente sin edición recorrió readiness, docs, perfil sin capacidades opcionales y review de import server-only | Satisfecho para escenarios evaluados; sin atribuir una adopción o feature adicional |
| [AC-05](specs/agent-development-loop/spec.md) | Distribución portable, expertise/guards preservados y entrega del mismo commit validado | Copier completo + agent-check del render de otra identidad exit 0; actionlint y parseo YAML GitLab exit 0; Codex/OpenCode comprobados. Claude 429 y pipelines remotos pendientes; GitHub main informó Branch not protected | Pendiente operativo; no cierre global |
| [AC-06](specs/schema-model-parity/spec.md) | Una cadena Alembic sin drift, datos válidos y unicidad conservados; errores explícitos | Empty/base y previa `20260707_000001` → `20260907_000002`, ambos sin drift; 3 tests PostgreSQL: owner/datos/uniqueness email-username-slug/delete SET NULL, huérfano con rollback, drift deliberado. DB inaccesible produce OperationalError y exit 1; dos heads en un grafo temporal se rechazan antes de crear DB | Satisfecho |

### Comandos, entorno y resultados

Node 24.18.1 / pnpm 11.1.2; OpenSpec 1.6.0 instalado desde el lock raíz. Python
3.14 y dependencias uv bloqueadas; PostgreSQL 17, Redis y Mailpit exclusivos por
invocación. Docker local disponible. No se usaron credenciales de usuarios reales.

| Comando / comprobación | Resultado observado |
| --- | --- |
| Baseline backend Ruff/ty/imports; frontend verify | Verdes antes de implementar. Node baseline fue 26; validación final usa 24 |
| `just verify` | Exit 0: agent-check, formato/lint/tipos/imports backend, 176 tests no API, frontend static + 13 tests en 4 archivos + build |
| `python3 scripts/test_stack.py all` | Exit 0: 195 tests, incluidos 19 API; warning previo de Authlib |
| `just backend check-migrations` (mismo runner `migrations` ejecutado) | Exit 0: DB vacía y previa sin drift; revisión inicial no editada |
| `python3 scripts/test_stack.py unit tests/common/database/test_migrations.py` | Exit 0: 3 tests, ampliados para las tres unicidades |
| `just backend check` final | Exit 0 después de corregir paréntesis de concatenación SQL en el test; sin cambio semántico |
| `pnpm -C frontend check:static` final | Exit 0; aviso previo no bloqueante de versión de schema Biome |
| `just integration` final | Exit 0: 2 specs sin interceptar la API; reportes Playwright por ejecución |
| Wrappers just con herramientas stub | 6 casos: default unit, filtro pytest con espacios, archivo Vitest con espacios, grep E2E, SQL con espacios y sync; cada valor conserva su argumento |
| `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` | Exit 0: 32 tests, incluidos negativos que imprimen errores esperados |
| `pnpm install --frozen-lockfile`; `just spec-check implement-agent-workflows`; `python3 scripts/check_specs.py` | Exit 0; CLI local, IDs/kind y artefactos comprobados |
| `pnpm -C docs types:check` y `pnpm -C docs build` | Exit 0; cambios finales de docs internas solo requieren enlaces/diff porque no alimentan el sitio renderizado |
| `actionlint`; parseo de `.gitlab-ci.yml` y `.gitlab/ci/*.yml` con soporte `!reference` | Exit 0 local; no certifica ejecución de proveedor |
| Copier sobre copia temporal Git de todos los archivos (incluidos nuevos); checks del render no default | Exit 0: round-trip, política Node, branding, configuración y sync. El índice real del usuario no se alteró |
| `git diff --check`; diff focalizado OpenSpec/opsx contra HEAD | Exit 0; contenido upstream intacto |

Logs locales de ejecución: `/tmp/wise-root-verify.log`, `/tmp/wise-backend-all.log`,
`/tmp/wise-backend-check-final.log`, `/tmp/wise-migrations.log`,
`/tmp/wise-migration-data.log`, `/tmp/wise-integration-negative.log`,
`/tmp/wise-integration-final.log`, `/tmp/wise-tooling-final.log`,
`/tmp/wise-template-final.log`. Son artefactos de esta sesión, no fixtures versionadas.
El resumen y los comandos anteriores permiten reproducirlos; CI publica los reports
Playwright. La observación de la suite técnica se reutiliza cuando ya demuestra el
criterio; no se contabiliza como una segunda prueba independiente.

### Discovery y activación

| Cliente / versión | CWD | Fuente efectiva / observación |
| --- | --- | --- |
| Codex 0.153.4 | raíz, backend, frontend | `debug prompt-input` muestra los siete; metadata duplicada .agents/.codex. Tres sesiones read-only activaron validate-change y abrieron `.agents/skills/validate-change/references/evidence.md` |
| OpenCode 1.17.11 | raíz, backend, frontend | `debug skill` muestra los siete; el origen de metadata varía entre .agents/.claude/.opencode. Tres sesiones con escritura/bash denegados activaron skill y leyeron recurso; no se asume orden estable de deduplicación |
| Claude Code 2.1.263 | raíz intentada; backend/frontend pendientes | Sesión limitada a Read/Skill recibió `api_error_status 429` por cuota. La igualdad de archivos no sustituye su smoke real |

Los smokes de raíz rechazaron checks verdes contradictorios; backend/frontend
rechazaron evidencia obsoleta tras modificar un contrato. La evaluación independiente
fue de lectura y un import in-memory, no un ciclo autónomo de creación de producto.
El ciclo ejecutado en este checkout comprende el rojo de drift Alembic, migración
correctiva, refinado/tests; y el contrato BFF rechazado, restauración, teclado y
recorrido real. No se afirma una segunda adopción real ni una medición comparativa
de coste/rendimiento de agentes.

### Revisión y límites del cierre

Se corrigieron los hallazgos: recursos no distribuidos, referencias incompatibles,
check Docker esperando DB, SMTP/clave de fixtures, expectativas incorrectas del
contrato E2E y gate de entrega que podía omitir la suite API. La matriz de prácticas
con sus destinos finales está en [el plan](../../../docs/arch_plan.md#16-registro-de-implementación).

Tras `just verify`, se ampliaron assertions del test de migración y el test E2E;
se renovaron sus pruebas y checks estáticos. Se ajustó el forwarding de argumentos
just con `$@` y se comprobaron seis invocaciones, incluidos espacios y valor default. El build y los tests de producto previos
siguen aplicando: no se modificaron fuentes runtime, dependencias ni contratos del
producto. La mutación BFF de ensayo se restauró byte por byte antes del gate final.
Cambios finales de referencias/docs/CI se validaron por agent-check, tooling,
OpenSpec, linters YAML y Copier; no requieren repetir suites de negocio verdes.

**Decisión global: implementación local entregable, aceptación operativa pendiente.**
No archivar/sincronizar estas normas como aceptadas mientras falten Claude y CI
remoto. `gh api .../branches/main/protection` devolvió 404 Branch not protected;
no se cambiaron settings remotos ni se presenta Required checks como protección
instalada. Publicar pipelines o activar protecciones requiere el flujo remoto del
repositorio. No se realizó merge, release o deploy.


## Refinado autorizado: responsabilidad de clean-fastapi-ddd

La auditoría posterior de los skills propios está documentada en
[ADR 0003](../../../docs/internal/adr/0003-auditoria-y-depuracion-de-skills.md).
Retira los dos skills redundantes, delimita las bibliotecas y evita duplicación
de los 17 skills mantenidos en discovery de Codex. Su registro incluye el nuevo
snapshot y evidencia de tooling, escenarios, clientes y Copier; la evidencia
funcional previa conserva su alcance y revisión originales.

El usuario pidió acotar este skill después de la entrega inicial. El propósito es
resolver decisiones arquitectónicas con una interfaz precisa, conservando expertise
y evitando otro workflow de implementación. Se mantiene el nombre para discovery.
Decisión: [ADR 0002](../../../docs/internal/adr/0002-responsabilidad-del-skill-de-arquitectura-backend.md).

- clean-fastapi-ddd conserva propiedad de conceptos, dependencias, casos de uso,
  repositorios/adapters, DI y presentación; referencias de capacidades condicionales.
- backend-change aloja la guía de scripts operativos; la ruta anterior remite a ella.
  El checklist describe conexiones, sin secuencias de tests/migraciones/commits.
- La referencia de pruebas identifica interfaces; verify-change/python-testing
  mantienen selección/evidencia y convenciones pytest. El perfil mantiene servicios,
  comandos y topología; los ejemplos de endpoints/bootstrap ya no exigen SERVER_MODE.
- Se corrigieron tres hallazgos de la evaluación: compartir sesión no garantiza
  atomicidad entre repositorios, el script no añade un commit tras repo.persist y
  los tests de excepciones async esperan execute, capturan el error esperado y
  lo comprueban con expects, según la convención confirmada por el usuario.

Evidencia de este refinado (2026-09-08):

| Comprobación | Resultado |
| --- | --- |
| quick_validate de clean-fastapi-ddd y backend-change | Exit 0; metadata y estructura válidas |
| just agent-check; tests de configuración y sync | Exit 0; 4 + 6 tests. Copias iguales y recursos enlazados en los destinos |
| Discovery Codex / OpenCode | Exit 0; ambos muestran la nueva descripción; OpenCode resolvió la copia .agents. No se repitió el smoke bloqueado por cuota de Claude |
| Evaluador independiente, lectura de cuatro solicitudes | Arquitectura de tenant settings permanece en guidance; regresión auth va a verify/python-testing; perfil sin tenancy/workers conserva esas ausencias; backfill usa backend-change. Hallazgos corregidos arriba |
| Ejecución de los dos ejemplos documentados de error async | Ambos usan expects y esperan execute; ausencia del error falla y errores inesperados se propagan. Sin DB |
| Tests backend de migraciones/imports alineados a expects | 7 casos focalizados y gate estático backend renovados; se conserva semántica de datos y límites de imports |
| Enlaces Markdown de skills afectados y recursos distribuidos | Todos resuelven; referencias útiles conservadas y ruta anterior de scripts compatible |
| Copier sobre copia Git temporal con archivos nuevos | Round-trip y branding verificados; no se modificó el índice real |
| Diff por contenido desde el inicio del refinado | Instrucciones, copias, documentación y aserciones de dos tests backend; fuentes runtime y tooling ejecutable permanecen iguales |
| Diff OpenSpec/opsx contra HEAD | Contenido upstream intacto |

Revisión final del refinado: **488a56eb117183c4e63d28188495539e0cc97497d56ce5b8aebaca206f87a88b**, HEAD
`fdf70798187e402b1529a0f72fe51f578a7d4917`, excluyendo este tasks.md como en el
comando de snapshot anterior. La evidencia previa de código de producto se reutiliza
porque las fuentes runtime y la configuración no cambiaron. Las aserciones de los
dos tests ajustados a expects se vuelven a ejecutar. La nueva metadata y referencias
se validan con los resultados de esta sección, no con los smokes de la versión anterior.
La aceptación de este ajuste documental no resuelve los pendientes operativos 1.4/3.3
ni archiva la change original.

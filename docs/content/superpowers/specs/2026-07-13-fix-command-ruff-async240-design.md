# Diseño para corregir Ruff en el CLI de fixtures

## Objetivo

Restablecer la validación exitosa de Ruff después de que se retiraran las
excepciones puntuales `ASYNC240` de `backend/command.py`, sin cambiar el
comportamiento del CLI de fixtures. También se elimina una configuración
obsoleta que intenta ignorar la regla retirada `UP038`.

## Contexto

Los comandos `load` y `dump` ejecutan consultas de base de datos asíncronas,
pero leen o escriben archivos pequeños de fixtures de manera síncrona. Este I/O
es deliberado: el proceso es un CLI de una sola ejecución y no atiende trabajo
concurrente mientras opera sobre esos archivos.

Ruff reporta `ASYNC240` en el `glob` de carga y en las dos escrituras de salida.
El commit `fcb4393` retiró exactamente los tres comentarios
`# noqa: ASYNC240` que documentaban estas excepciones; el commit posterior
`116089b` solo reformateó las escrituras. Además, Ruff avisa que `UP038` ya no
existe, aunque permanece dentro de `lint.ignore`.

## Diseño

Se restaurará `# noqa: ASYNC240` únicamente en estas operaciones:

1. `pathlib.Path(fixtures_dir).glob("*.*")`;
2. la escritura YAML de `dump`;
3. la escritura JSON de `dump`.

Las excepciones permanecen en línea para que no oculten nuevas llamadas
bloqueantes en otras partes del archivo. No se deshabilita `ASYNC240` globalmente
ni para todo `command.py`.

Se retirará `UP038` de `backend/ruff.toml`, junto con su comentario, porque
ignorar una regla eliminada no tiene efecto y genera ruido en CI.

## Alcance y compatibilidad

No cambian las firmas, formatos de fixtures, acceso a base de datos, mensajes
del CLI ni dependencias. Se preservan los cambios locales existentes en
`backend/command.py`. No se introduce `asyncio.to_thread` ni `anyio.Path`, pues
el CLI no obtiene un beneficio observable de mover estas operaciones pequeñas a
un thread o a otro adaptador de filesystem.

## Verificación

1. `cd backend && uv run ruff check .` debe completar sin `ASYNC240` ni el
   aviso de `UP038`.
2. `cd backend && uv run ruff format --check .` debe confirmar el formato del
   backend.
3. `just template check` debe confirmar que ambos cambios viajan correctamente
   a proyectos generados.
4. `git diff --check` debe completar sin errores de whitespace.
5. El diff funcional debe limitarse a tres excepciones de línea y a retirar la
   entrada obsoleta de Ruff.

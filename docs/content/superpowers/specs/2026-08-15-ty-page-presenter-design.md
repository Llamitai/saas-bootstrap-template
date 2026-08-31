# Reparación tipada de la presentación de páginas

## Contexto

El PR de Dependabot #117 actualiza `ty` de 0.0.59 a 0.0.70. La nueva versión
detecta que `Page[T].apply_presenter()` sustituye `list[T]` por
`list[dict[str, Any]]` dentro de la misma instancia. Esa mutación contradice el
parámetro genérico de `Page` aunque el JSON producido en ejecución sea válido.

## Decisión

`Page[T].apply_presenter()` dejará de mutar la página original y devolverá una
nueva `Page[dict[str, Any]]`. La nueva página conservará `next_cursor` y
`limit`, y transformará cada elemento mediante el presenter recibido.

Los dos endpoints consumidores asignarán el valor devuelto antes de construir
`ApiJSONResponse`. El contrato HTTP no cambia: `data` seguirá siendo la lista de
diccionarios presentada y `pagination` conservará el mismo cursor y límite.

## Alternativas descartadas

- Introducir un `map[U]` genérico permitiría más transformaciones, pero amplía
  la interfaz sin una necesidad actual.
- Usar `cast`, `Any` o una supresión de diagnóstico mantendría la mutación y
  ocultaría un contrato de tipos incorrecto.
- Ampliar `items` a una unión entre entidades y diccionarios contaminaría todos
  los consumidores de `Page[T]` con un estado que sólo necesita presentación.

## Flujo

1. El repositorio y el caso de uso producen `Page[T]` con entidades de dominio.
2. El endpoint llama a `apply_presenter()` y recibe `Page[dict[str, Any]]`.
3. `ApiJSONResponse` serializa los elementos presentados y la paginación igual
   que antes.

La página original permanece intacta. Si un presenter falla, la excepción se
propaga como en el comportamiento actual; no se introduce manejo de errores
nuevo.

## Verificación

- Añadir pruebas unitarias que comprueben la transformación, la conservación de
  cursor y límite, y que la página original no se modifica.
- Ejecutar `uv lock --offline` para demostrar que el lockfile del PR es
  reproducible.
- Ejecutar la calidad del backend, incluido `ty` 0.0.70 e import-linter.
- Ejecutar todos los tests del backend y los checks remotos del PR de reemplazo.

El PR de reemplazo incluirá la actualización de Dependabot y esta reparación;
cuando se fusione, el PR #117 se cerrará como reemplazado.

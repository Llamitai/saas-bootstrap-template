---
title: "0002 — Responsabilidad del skill de arquitectura backend"
---

Estado: aceptado por la petición de acotar el skill, 2026-09-08.
Complementa [ADR 0001](0001-ciclo-de-cambios-y-verificacion.md).

## Contexto y drivers

`clean-fastapi-ddd` se describía como biblioteca, pero su activación abarcaba casi
cualquier tarea backend. También mantenía secuencias de tests, migraciones,
operación y commits que se solapaban con los workflows del proyecto. Algunas
referencias convertían SAQ o los modos de despliegue en requisitos universales.

## Opciones y decisión

Se acota la interfaz del skill a resolver decisiones de arquitectura: propiedad de
conceptos, dependencias, casos de uso, repositorios/adapters, DI y presentación.
Se conserva una biblioteca con referencias bajo demanda; dividir cada referencia
en un skill independiente añadiría entradas de discovery sin resolver el solapamiento.

`backend-change` conduce implementación/refinado y aloja la guía de scripts
operativos. `schema-change` conduce evolución de datos. `verify-change` selecciona
verificaciones y evidencia, con `python-testing` para las convenciones pytest.
El perfil y la guía de verificación mantienen capacidades, comandos y entornos.

El checklist de módulos pasa a describir conexiones arquitectónicas. La referencia
de pruebas identifica las interfaces de cada capa y remite a sus responsables;
no mantiene otro manual pytest. Se conserva la ruta previa de scripts como enlace.
Auth, CQRS, paginación, jobs y bootstrap conservan sus patrones condicionales.

## Consecuencias

La descripción de discovery deja de competir por cualquier trabajo backend.
Resolver una pregunta arquitectónica no inicia otro ciclo de implementación o
aceptación. Las convenciones detalladas tienen una fuente y los workflows la
consultan; cambiar una convención no requiere repetirla en el workflow.

Se mantienen nombre del skill y rutas compatibles, sincronizadas desde `.claude`.
Este ajuste modifica instrucciones, no comportamiento, persistencia ni dependencias
del producto. Se verifican metadata, enlaces, distribución y decisiones de selección;
los skills OpenSpec y comandos opsx conservan su contenido.

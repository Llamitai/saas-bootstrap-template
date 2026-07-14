# Documentación interna (`docs/internal/`)

Esta carpeta contiene documentación técnica no renderizada para el core del
boilerplate. Debe mantenerse centrada en auth, tenancy, members, roles,
settings, profile, messaging, Directus/admin y arquitectura frontend/backend.

La documentación ajena a esta plantilla debe eliminarse en vez de conservarse
como histórico dentro del repositorio.

## Mapa

- `architecture/frontend-architecture.md`: fuente de verdad para estructura e
  imports del frontend.
- `architecture/erd-diagram.md`: ERD reducido de la base core.
- `backend/api-reference.md`: rutas REST core.
- `backend/api/tenant-users.md`: detalle operativo de members/invitations.
- `backend/debugging.md`: debugging local del backend.
- `adr/`: decisiones activas del boilerplate. Si no hay ADR aceptado para el
  core, mantener solo el índice.

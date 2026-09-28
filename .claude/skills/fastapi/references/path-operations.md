# Path operations and routers

FastAPI's `APIRouter` accepts a prefix, tags and shared dependencies; route
registration can also provide method-specific metadata. Inspect the installed
FastAPI API when a parameter or composition behavior is unclear.

In this project, presentation routers register endpoints with
`add_api_route()`, one HTTP operation per endpoint. Follow a matching router in
`backend/src/` for the placement of prefixes, tags, dependencies, response
models and status codes. Generic decorator examples from FastAPI documentation
describe framework syntax but do not replace this project pattern.

If a route, parameter, response model, tag or summary changes, follow
`openapi-sync` to refresh and verify `docs/openapi/openapi.json`.

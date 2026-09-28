# Response schemas

FastAPI can derive a public schema from a return annotation or from
`response_model`. The latter can document, validate and filter the declared
shape. Check the installed FastAPI version when the exact behavior matters.

In this project, every route declares its `response_model` and actual
`status_code`. Endpoints return `ApiJSONResponse`; presenters and the response
class own the public envelope and camelCase conversion. A generic example that
returns a Pydantic model directly does not establish the application's wire
format. Inspect a matching endpoint, presenter and response class before
changing serialization or exposure of fields.

HTTP response changes also require the relevant backend tests and
`openapi-sync`.

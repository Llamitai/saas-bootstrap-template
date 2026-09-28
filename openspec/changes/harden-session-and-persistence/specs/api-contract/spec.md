## ADDED Requirements

### Requirement: AC-04 OpenAPI matches the wire format
The OpenAPI schema SHALL document every successful response with its envelope and camelCase fields, request bodies with camelCase aliases, and no parameters the endpoint does not accept.

#### Scenario: Generated reference
- **WHEN** the snapshot is exported
- **THEN** every operation declares a 2xx schema, request properties are camelCase, operationIds are readable and PUT /v1/me/password has no query parameters

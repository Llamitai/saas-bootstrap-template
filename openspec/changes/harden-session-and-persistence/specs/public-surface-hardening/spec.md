## ADDED Requirements

### Requirement: AC-05 Supported token library
JWT issuance and validation SHALL use a maintained JOSE library, keep accepting tokens issued before the change, and validate the Google ID token issuer.

#### Scenario: Token compatibility and issuer
- **WHEN** a token issued with the previous library is validated, or a Google ID token has an unexpected issuer
- **THEN** the former is accepted and the latter is rejected

### Requirement: AC-06 Public endpoints resist abuse without blocking the loop
Registration SHALL be rate limited and ignore privilege fields; password hashing SHALL run off the event loop; error reporting SHALL not send PII by default.

#### Scenario: Registration burst
- **WHEN** a client exceeds the registration limit or sends isSuperuser
- **THEN** it receives 429 after the limit and the created user is never a superuser

### Requirement: AC-07 Container health
The API SHALL expose a dependency-free liveness endpoint and a readiness endpoint that checks the database and Redis.

#### Scenario: Dependency down
- **WHEN** the database is unreachable
- **THEN** /api/py/health answers 200 and /api/py/health/ready answers 503

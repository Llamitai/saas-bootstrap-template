## ADDED Requirements

### Requirement: AC-03 Performance without losing security state
The cache store SHALL use Valkey tuned for throughput while never evicting keys and persisting writes, so revoked tokens stay revoked across memory pressure and restarts.

#### Scenario: Store configuration
- **WHEN** the development stack starts
- **THEN** Valkey reports maxmemory-policy noeviction, appendonly yes and more than one I/O thread

### Requirement: AC-04 Services available to every gate
CI, the template preflight and the development stack SHALL provide Valkey and RabbitMQ to the backend tests.

#### Scenario: Backend suite in CI
- **WHEN** the Code Quality backend job or the template preflight runs pytest
- **THEN** tests that need Valkey or RabbitMQ connect and pass

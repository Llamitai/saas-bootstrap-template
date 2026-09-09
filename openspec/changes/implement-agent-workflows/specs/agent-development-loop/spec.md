## ADDED Requirements

### Requirement: AC-01 Required skill distribution
The kit SHALL distribute all seven workflows and their resources to each declared client subset and reject missing, altered, orphaned or unsafe paths without repairing during checks.

#### Scenario: Required copy disappears
- **WHEN** a required workflow or resource is removed from a destination
- **THEN** agent-check fails and a subsequent explicit sync repairs it idempotently

### Requirement: AC-02 Reproducible commands
The kit SHALL expose non-mutating static checks, locked OpenSpec wrappers and a feature generator that preserves existing user code.

#### Scenario: Invalid selection
- **WHEN** a spec ID/type is invalid, no E2E tests match, or a feature already exists
- **THEN** the command fails with a useful error and does not overwrite sources

### Requirement: AC-03 Isolation and integration
The kit SHALL test real browser-to-BFF-to-API session behavior with exclusive services and clean only resources created by its run.

#### Scenario: Login error and recovery
- **WHEN** a newly provisioned test user submits invalid then valid credentials and logs out
- **THEN** the UI exposes recovery, the BFF establishes HttpOnly cookies and logout clears them

### Requirement: AC-04 Acceptance is distinct from verification
Workflows SHALL reuse approved definitions, trace criteria to the tested revision, reject stale or contradictory evidence, and keep incomplete archives distinct from delivered behavior.

#### Scenario: Green checks contradict acceptance
- **WHEN** tests pass but an observed required result differs from its normative criterion
- **THEN** validate-change fails and returns to the implementer without changing the criterion

### Requirement: AC-05 Portable configuration and delivery
The kit SHALL preserve specialized practices, distributed provider checks and canonical template guards, and bind deployment builds to successful validation of the same commit.

#### Scenario: Adopting another identity
- **WHEN** Copier renders the kit with another identity
- **THEN** operational workflows, resources and checks work without private paths or a runtime dependency on canonical template publishing

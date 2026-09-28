## ADDED Requirements

### Requirement: AC-02 Repository writes are durable
Every repository write SHALL be committed before the method returns, without relying on a later call to commit the shared session.

#### Scenario: Flush-only write
- **WHEN** an email address or phone number is created through get_or_create, or a user is removed, and the session then closes
- **THEN** a new session observes the created or removed row

### Requirement: AC-03 Nested transactions stay atomic
A transaction helper opened inside another SHALL not commit the outer transaction; a failure in the outer block SHALL roll back the inner writes.

#### Scenario: Outer failure after inner write
- **WHEN** an inner atomic_transaction writes a row and the outer block then raises
- **THEN** no row from either block is persisted

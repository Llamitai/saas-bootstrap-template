## ADDED Requirements

### Requirement: AC-06 Real migration parity
The backend SHALL upgrade empty and supported prior databases to one head and have no model drift, preserving existing valid user/tenant data and uniqueness.

#### Scenario: Upgrade initial core with existing data
- **WHEN** the initial revision contains a valid tenant owner and is upgraded
- **THEN** the owner relationship remains, unique email/username/slug remain enforced and deleting that owner sets the reference null

#### Scenario: Existing invalid owner
- **WHEN** a prior database references an owner absent from users
- **THEN** upgrade fails explicitly without deleting or silently rewriting that tenant

#### Scenario: Conflict or drift
- **WHEN** a revision graph has multiple heads or a migrated schema differs from ORM
- **THEN** check-migrations fails and removes only its disposable databases

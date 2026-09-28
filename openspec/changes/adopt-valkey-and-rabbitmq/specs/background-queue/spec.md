## ADDED Requirements

### Requirement: AC-01 Durable delivery
An asynchronous command SHALL be published persistently with broker confirmation and executed by the worker, which acknowledges it only after the handler succeeds.

#### Scenario: Command executed once published
- **WHEN** a command is dispatched with run_async and the worker is running
- **THEN** its handler runs and the message is acknowledged

#### Scenario: Broker rejects the publish
- **WHEN** the broker does not confirm or cannot route the message
- **THEN** the dispatch raises instead of dropping the command

### Requirement: AC-02 Bounded retries and dead-letter
A failing command SHALL be redelivered up to the configured limit and then moved to a dead-letter queue; a malformed message SHALL go to the dead-letter queue without retries.

#### Scenario: Handler keeps failing
- **WHEN** the handler raises on every attempt
- **THEN** the message ends in the dead-letter queue after the delivery limit

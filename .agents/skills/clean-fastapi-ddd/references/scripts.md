# Operational scripts

The implementation guidance for backfills, bootstrappers, dry-run/apply behavior,
reports and bounded batches belongs to
[backend-change's operational-scripts reference](../../backend-change/references/operational-scripts.md).
This path remains available for existing callers.

For the architectural connection, use [dependency-injection.md](dependency-injection.md)
to construct the context outside HTTP and [repositories.md](repositories.md) to
preserve the persistence interface and transaction lifecycle.

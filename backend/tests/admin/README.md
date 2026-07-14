# admin tests

`src/admin` is a presentation-only facade (endpoints dispatch commands via the bus behind an admin API key); it has no unit-testable surface without the running stack, so its coverage lives in the `api`-marked E2E suite (`tests/api`, run with the docker stack up).

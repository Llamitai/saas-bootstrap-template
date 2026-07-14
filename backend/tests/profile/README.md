# profile tests

`src/profile` is a presentation-only facade (endpoints wrap authenticated-session dependencies and bus dispatch); it has no unit-testable surface without the running stack, so its coverage lives in the `api`-marked E2E suite (`tests/api`, run with the docker stack up).

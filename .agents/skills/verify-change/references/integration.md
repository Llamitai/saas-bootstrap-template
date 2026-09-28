# Integration verification

Use the isolated integration runner in docs/content/docs/equipo/verificacion.md. Distinguish frontend smoke, mocked network and real API journeys. Verify requests, response casing/envelopes, errors, active headers/cookies and consumed data. A real browser -> BFF -> API test must fail if that contract is made incompatible in a disposable fixture. Use exclusive DB/Compose/ports/browser state, bounded readiness and cleanup in finally/traps. Never attach to or delete another task's services.

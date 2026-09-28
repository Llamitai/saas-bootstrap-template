## ADDED Requirements

### Requirement: AC-01 Session survives reloads and tenant switches
The frontend SHALL rotate refresh tokens only where the new cookies can be written, so a signed-in user keeps the session across hard reloads, protected navigations and tenant switches.

#### Scenario: Reload inside a tenant
- **WHEN** a user with an active tenant signs in, reloads a protected page twice and switches tenant
- **THEN** each response renders the protected page and the browser's refresh cookie is still accepted by the backend

#### Scenario: Expired access token on navigation
- **WHEN** the access cookie is missing or expired and the refresh cookie is valid
- **THEN** the proxy rotates the session, sets both cookies on the response and the page renders without redirecting to login

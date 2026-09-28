## ADDED Requirements

### Requirement: AC-05 Only the current token of a session refreshes
A refresh SHALL be accepted only when its jti equals the current jti stored for its session; any earlier or closed-session token SHALL receive 401.

#### Scenario: Rotated token reused after the grace window
- **WHEN** a refresh token that was already rotated is presented after the grace window
- **THEN** the backend answers 401

### Requirement: AC-06 Configurable sessions per user
With JWT_MAX_SESSIONS_PER_USER set to N, a login that exceeds N SHALL close the least recently used session while the others keep refreshing.

#### Scenario: Third login with N=2
- **WHEN** a user logs in three times with N=2
- **THEN** the first session gets 401 on refresh and the other two refresh successfully

### Requirement: AC-07 Session and account revocation
Logout SHALL close only its session; a password change or reset SHALL close every session of the user.

#### Scenario: Password reset
- **WHEN** a user with two sessions resets the password
- **THEN** both refresh tokens receive 401

### Requirement: AC-08 Grace window per session
The rotation grace window SHALL return the same pair only while the session still holds that rotation, never for a closed or evicted session.

#### Scenario: Logout within grace
- **WHEN** a session is closed during the grace window and the old token is presented
- **THEN** the backend answers 401

### Requirement: AC-09 Fail-closed store
Losing or evicting any session key SHALL only produce 401, never accept a revoked token, so the cache store can evict with allkeys-lru.

#### Scenario: Index evicted
- **WHEN** the session index or a session key disappears
- **THEN** affected refreshes answer 401 and no revoked token is accepted

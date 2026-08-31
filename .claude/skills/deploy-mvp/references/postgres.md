# PostgreSQL provisioning reference

Targets PostgreSQL 15, 16 and 17. `scripts/provision_db.py` implements all of
this; read here when you want to run it by hand or understand why a step
exists.

## The standard recipe, corrected

The usual four-liner is directionally right but incomplete:

```sql
CREATE USER <u> WITH PASSWORD '<pw>';
GRANT <u> TO CURRENT_USER;
CREATE DATABASE <db> OWNER <u>;
GRANT ALL PRIVILEGES ON DATABASE <db> TO <u>;   -- does NOT do what you think
```

What it gets right, and what it misses:

### `GRANT <u> TO CURRENT_USER` — required, and the order matters

`CREATE DATABASE … OWNER <u>` demands membership in `<u>`. PG15 words it "you
must be a direct or indirect member of that role, or be a superuser"; PG16/17
tighten it to "you must be able to `SET ROLE` to that role".

It must sit **between** `CREATE ROLE` and `CREATE DATABASE`. Reversed, you get
`ERROR: must be member of role "<u>"`.

Skip it only when the admin is a superuser.

> **PG16 trap:** a `CREATEROLE` non-superuser is implicitly granted the roles it
> creates — but that implicit grant carries `SET FALSE`, so it does **not**
> satisfy the `SET ROLE` requirement. Only an explicit `GRANT` (whose `SET`
> option defaults to true) or `SET createrole_self_grant = 'set'` works.

### `GRANT ALL PRIVILEGES ON DATABASE` — a no-op here

Database-level `ALL` means `CREATE` (create *schemas*) + `CONNECT` +
`TEMPORARY`. It is **not** the right to create tables, and it is redundant when
the role already owns the database.

### The grant you actually need — PG15+ schema privileges

PostgreSQL 15 removed `PUBLIC`'s `CREATE` privilege on the `public` schema.
This is what produces:

```
ERROR: permission denied for schema public
```

during migrations. Fix it **while connected to the new database** — schema ACLs
are per-database and PostgreSQL has no cross-database DDL:

```sql
\c <db>
GRANT USAGE, CREATE ON SCHEMA public TO <u>;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CONNECT ON DATABASE <db> FROM PUBLIC;
```

> **Prefer the grant over `ALTER SCHEMA public OWNER TO <u>`.** Since PG15,
> `public` is owned by `pg_database_owner`, an implicit role whose membership
> resolves to whoever owns the current database — so the app role already
> benefits. Reassigning real ownership breaks that indirection, hands the role
> `DROP`/`ALTER` rights on the schema it never needs, and shows up as a diff in
> `pg_dump` output.

The `REVOKE`s are explicit rather than assumed: a cluster `pg_upgrade`d from
PostgreSQL 14 or earlier carries `template1`'s permissive `public` schema
forward, so new databases inherit pre-15 defaults.

## Idempotency

There is **no `IF NOT EXISTS`** for `CREATE ROLE` or `CREATE DATABASE` (only
`CREATE SCHEMA` has it). `DROP` has `IF EXISTS` for both.

`CREATE DATABASE` **cannot run inside a transaction block**, which rules out
`DO $$ … $$`, PL/pgSQL, `psql --single-transaction`, and any multi-statement
`-c` string (psql sends one `-c` as a single request, executed as one
transaction).

The sanctioned pattern is `SELECT … \gexec`, which sends each generated query
as its own request and executes zero rows as a no-op:

```sql
SELECT 'CREATE DATABASE ' || quote_ident(:'db') || ' OWNER ' || quote_ident(:'role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db')
\gexec
```

A role *can* be created inside a `DO` block, so that one is guardable normally:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'acme') THEN
        CREATE ROLE acme LOGIN PASSWORD '…';
    END IF;
END
$$;
```

## Safe invocation

```bash
PGPASSWORD="$PW" psql -X -v ON_ERROR_STOP=1 -h host -U postgres -d postgres
```

- `-X` skips `~/.psqlrc`, so an operator's local settings cannot change results.
- `-v ON_ERROR_STOP=1` aborts on the first error. Without it psql keeps going
  and exits 0 after a failed `CREATE`.
- Exit codes: **1** psql fatal, **2** connection lost, **3** SQL error with
  `ON_ERROR_STOP`. Checking `!= 0` is fine; do not assume 1.

### Identifiers vs literals

PostgreSQL has **no bind parameter for identifiers**. Validate names against a
strict pattern and reject anything else — that validation is the security
boundary. `provision_db.py` enforces `^[a-z][a-z0-9_]{0,62}$`.

Two psql traps:

- `:var` is **not** interpolated inside quoted literals: `':foo'` is the
  literal text `:foo`. The same applies inside dollar-quoted bodies, so
  `DO $$ … :'role' … $$` silently ships the wrong text.
- `\getenv psql_var env_var` (the clean way to keep a password out of `argv`)
  exists in **psql 16+** only — the constraint is the client version.

### Keeping the password out of view

Anything in `-v pw=…` or in a connection URI on the command line is visible to
other users via `ps`. Use `PGPASSWORD`, a quoted heredoc, `\getenv` (16+), or a
`0600` SQL file.

Separately: `CREATE ROLE … PASSWORD 'literal'` lands in the **server log** when
`log_statement` is `ddl` or `all`. On a shared server, rotate afterwards or
provision during a window where that is acceptable.

## Password generation

```bash
openssl rand -base64 32          # emits + / = — all need percent-encoding in a URI
```

`+`, `/` and `=` must be percent-encoded in a URI userinfo field, and `+` is
parser-dependent. Restrict the alphabet at generation time instead —
`provision_db.py` uses only URL-unreserved characters
(`A–Z a–z 0–9 - . _ ~`), so the value drops into a DSN unencoded.

> `postgresql+asyncpg://` is a **SQLAlchemy dialect string**, not a libpq URI.
> `psql`, `pg_dump` and `pgbench` reject it. Keep a plain `postgresql://` copy
> for CLI tooling.

## Verification

```sql
SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = 'acme';
SELECT datname, pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'acme';
-- connected to the new database:
SELECT has_schema_privilege('acme', 'public', 'CREATE');   -- must be true
```

Then connect as the new role and create a throwaway table — that is the only
check that proves migrations will work.

## Rollback

```sql
-- In EVERY database the role owns objects in:
REASSIGN OWNED BY <u> TO postgres;
DROP OWNED BY <u>;
-- Then, from another database:
DROP DATABASE IF EXISTS <db> WITH (FORCE);
DROP ROLE IF EXISTS <u>;
```

`REASSIGN OWNED` and `DROP OWNED` **do not cross database boundaries** — run
them in each database containing objects owned by the role. `DROP OWNED` will
not drop databases or tablespaces. `REASSIGN OWNED` will not clear
`ALTER DEFAULT PRIVILEGES` entries; only `DROP OWNED` does. Run `REASSIGN` then
`DROP OWNED`, in that order, then `DROP ROLE`.

`WITH (FORCE)` (PG13+) terminates existing connections so the drop does not
block.

## This project's two databases

The backend stack runs Directus as its admin console, and Directus needs its
**own** database — it manages its own schema and will collide with the
application's migrations otherwise.

```
<slug>            -> application    (POSTGRES_DB)
<slug>_directus   -> Directus       (ADMIN_DB_DATABASE)
```

Both can share one role. `provision_db.py --with-directus` creates the pair.

#!/usr/bin/env python3
"""Provision a per-project PostgreSQL role and database(s), idempotently.

Standard library only. Shells out to `psql`, which must be on PATH.
If you do not have psql locally, run this through the postgres image instead:

    docker run --rm -i -v "$PWD:/w" -w /w postgres:17-alpine \\
        python3 - < scripts/provision_db.py ...

Creates:
  * a LOGIN role  <name>          with a generated, DSN-safe password
  * a database    <name>          owned by that role
  * a database    <name>_directus owned by that role   (--with-directus)

and applies the PostgreSQL 15+ schema grants that `GRANT ALL PRIVILEGES ON
DATABASE` does NOT cover. Without them, migrations fail with
"permission denied for schema public".

Generated credentials are written to `.env.deploy.generated` (gitignored) for
the Infisical seeding phase to consume. Values are never printed.

Usage:
    provision_db.py --env-file .env.deploy --name acme --dry-run
    provision_db.py --env-file .env.deploy --name acme --with-directus
    provision_db.py --env-file .env.deploy --name acme --verify
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import string
import subprocess
import sys
from pathlib import Path

# URL-unreserved characters only: a generated password made of these needs no
# percent-encoding inside a postgresql:// DSN, so it can never break a
# connection string or a compose file.
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-._~"
PASSWORD_LENGTH = 40

# Deliberately strict. These names are interpolated into SQL as identifiers,
# and PostgreSQL has no bind-parameter form for identifiers, so validation is
# the security boundary. Anything outside this set is rejected rather than
# quoted-and-hoped-for.
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ProvisionError(RuntimeError):
    pass


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv file. Ignores comments, blanks, and `export ` prefixes."""
    if not path.is_file():
        raise ProvisionError(f"env file not found: {path}")
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def require_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.match(value):
        raise ProvisionError(
            f"{label} {value!r} is not a safe SQL identifier. "
            "Use lowercase letters, digits and underscores, starting with a "
            "letter, max 63 characters."
        )
    return value


def generate_password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def sql_literal(value: str) -> str:
    """Quote a string as a SQL literal. Only used for passwords."""
    return "'" + value.replace("'", "''") + "'"


def psql_env(env: dict[str, str]) -> dict[str, str]:
    """Build the environment for psql. Password travels via PGPASSWORD, never argv."""
    out = dict(os.environ)
    for key in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGSSLMODE"):
        if env.get(key):
            out[key] = env[key]
    out.setdefault("PGDATABASE", "postgres")
    out.setdefault("PGCONNECT_TIMEOUT", "10")
    return out


def run_psql(
    sql: str,
    env: dict[str, str],
    *,
    dbname: str | None = None,
    quiet: bool = False,
) -> str:
    """Execute SQL through psql, aborting on the first error."""
    cmd = ["psql", "-v", "ON_ERROR_STOP=1", "--no-psqlrc", "-X"]
    if quiet:
        cmd += ["-tA", "-q"]
    if dbname:
        cmd += ["-d", dbname]
    proc = subprocess.run(
        cmd,
        input=sql,
        text=True,
        capture_output=True,
        env=psql_env(env),
    )
    if proc.returncode != 0:
        stderr = redact(proc.stderr.strip(), env)
        raise ProvisionError(f"psql failed:\n{stderr}")
    return proc.stdout.strip()


def redact(text: str, env: dict[str, str]) -> str:
    """Strip anything that looks like a credential out of tool output."""
    for key in ("PGPASSWORD", "INFISICAL_MACHINE_CLIENT_SECRET", "PORTAINER_TOKEN"):
        value = env.get(key)
        if value and len(value) > 3:
            text = text.replace(value, f"<{key}>")
    return text


# ── SQL builders ─────────────────────────────────────────────────────


def role_sql(role: str, password: str) -> str:
    """Create the login role if absent; reset its password if present.

    `GRANT <role> TO CURRENT_USER` makes the connecting user a member of the new
    role. PostgreSQL requires this membership before it will let a non-superuser
    create a database OWNED BY that role. A superuser already satisfies the
    check, but the grant is harmless there, so it runs unconditionally rather
    than branching on the server version.
    """
    return f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
        CREATE ROLE {role} LOGIN PASSWORD {sql_literal(password)};
        RAISE NOTICE 'created role {role}';
    ELSE
        ALTER ROLE {role} WITH LOGIN PASSWORD {sql_literal(password)};
        RAISE NOTICE 'role {role} already existed; password rotated';
    END IF;
END
$$;

GRANT {role} TO CURRENT_USER;
""".strip()


def database_sql(dbname: str, owner: str) -> str:
    """Create the database if absent.

    CREATE DATABASE cannot run inside a transaction block, which rules out
    DO $$ ... $$. The standard workaround is to SELECT the statement text and
    feed it back to the server with psql's \\gexec, which executes zero rows as
    a no-op — making this idempotent.
    """
    return f"""
SELECT 'CREATE DATABASE {dbname} OWNER {owner}'
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '{dbname}')\\gexec
""".strip()


def grants_sql(dbname: str, role: str) -> str:
    """Grants applied while connected to the new database.

    Schema ACLs are per-database, so these MUST run against the new database —
    PostgreSQL has no cross-database DDL.

    PostgreSQL 15 removed the CREATE privilege PUBLIC used to hold on the
    `public` schema, which is what breaks migrations with
    "permission denied for schema public". The fix is a schema-level grant.
    `GRANT ALL PRIVILEGES ON DATABASE` does NOT fix it and is a no-op here
    anyway: database-level ALL means CREATE-schema/CONNECT/TEMPORARY, and the
    role already owns the database.

    Deliberately NOT `ALTER SCHEMA public OWNER TO <role>`: since PG15 `public`
    is owned by `pg_database_owner`, an implicit role whose membership resolves
    to whoever owns the current database. The app role already benefits from
    that indirection. Reassigning real ownership breaks it, hands the role
    DROP/ALTER rights on the schema it never needs, and shows up as a diff in
    pg_dump output.

    The REVOKEs are explicit rather than assumed: a cluster pg_upgraded from
    PostgreSQL 14 or earlier carries template1's old permissive public schema
    forward, so new databases inherit the pre-15 defaults.
    """
    return f"""
GRANT USAGE, CREATE ON SCHEMA public TO {role};
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CONNECT ON DATABASE {dbname} FROM PUBLIC;
""".strip()


def build_plan(role: str, databases: list[str], password: str) -> list[tuple[str, str, str]]:
    """Return [(description, target_db, sql)] in execution order."""
    plan: list[tuple[str, str, str]] = [
        (f"create/refresh role {role}", "", role_sql(role, password)),
    ]
    for dbname in databases:
        plan.append((f"create database {dbname}", "", database_sql(dbname, role)))
    for dbname in databases:
        plan.append((f"grants on {dbname}", dbname, grants_sql(dbname, role)))
    return plan


# ── Commands ─────────────────────────────────────────────────────────


def cmd_provision(args: argparse.Namespace, env: dict[str, str]) -> int:
    role = require_identifier(args.name, "role name")
    databases = [require_identifier(args.name, "database name")]
    if args.with_directus:
        databases.append(require_identifier(f"{args.name}_directus", "directus database name"))

    password = generate_password()
    plan = build_plan(role, databases, password)

    if args.dry_run:
        print("# DRY RUN — no statements executed.")
        print(f"# role:      {role}")
        print(f"# databases: {', '.join(databases)}")
        print("# password:  <generated at apply time, 40 chars, URL-safe>\n")
        for description, dbname, sql in plan:
            where = f" (connected to {dbname})" if dbname else ""
            print(f"-- {description}{where}")
            print(sql.replace(sql_literal(password), "'<generated>'"))
            print()
        print("# Re-run without --dry-run to apply.")
        return 0

    for description, dbname, sql in plan:
        print(f"-> {description} ...", end=" ", flush=True)
        run_psql(sql, env, dbname=dbname or None, quiet=True)
        print("ok")

    written = write_generated(
        Path(args.output),
        role=role,
        password=password,
        databases=databases,
        env=env,
        with_directus=args.with_directus,
    )
    print(f"\nWrote {len(written)} keys to {args.output} (values not shown):")
    for key in written:
        print(f"  {key}")
    print("\nNext: phase 2 — seed Infisical with these overrides.")
    return 0


def write_generated(
    path: Path,
    *,
    role: str,
    password: str,
    databases: list[str],
    env: dict[str, str],
    with_directus: bool,
) -> list[str]:
    """Write generated credentials for the Infisical seeding phase.

    Merges into an existing file rather than truncating it, so re-running one
    phase does not discard another phase's output.
    """
    host = env.get("APP_POSTGRES_HOST") or env.get("PGHOST", "")
    port = env.get("APP_POSTGRES_PORT") or env.get("PGPORT", "5432")

    values = {
        "POSTGRES_USER": role,
        "POSTGRES_PASSWORD": password,
        "POSTGRES_DB": databases[0],
        "POSTGRES_HOST": host,
        "POSTGRES_PORT": port,
    }
    if with_directus:
        values.update(
            {
                "ADMIN_DB_USER": role,
                "ADMIN_DB_PASSWORD": password,
                "ADMIN_DB_DATABASE": databases[1],
                "ADMIN_DB_HOST": host,
            }
        )

    existing = load_env_file(path) if path.is_file() else {}
    existing.update(values)

    lines = ["# Generated by deploy-mvp/scripts/provision_db.py. Do not commit."]
    lines += [f"{key}={value}" for key, value in sorted(existing.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return sorted(values)


def cmd_verify(args: argparse.Namespace, env: dict[str, str]) -> int:
    role = require_identifier(args.name, "role name")
    databases = [role] + ([f"{role}_directus"] if args.with_directus else [])

    print("Server:")
    print("  " + run_psql("SELECT version();", env, quiet=True).splitlines()[0])

    print("\nRole:")
    found = run_psql(
        f"SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = '{role}';",
        env,
        quiet=True,
    )
    print(f"  {found or '(MISSING)'}")

    print("\nDatabases:")
    ok = bool(found)
    for dbname in databases:
        row = run_psql(
            "SELECT d.datname, pg_catalog.pg_get_userbyid(d.datdba) AS owner "
            f"FROM pg_database d WHERE d.datname = '{dbname}';",
            env,
            quiet=True,
        )
        print(f"  {row or f'{dbname} (MISSING)'}")
        ok = ok and bool(row)

    # What matters is the PRIVILEGE, not the ownership. Since PG15 the public
    # schema is owned by pg_database_owner, an implicit role that resolves to
    # the database owner — so a correct setup shows an owner of
    # `pg_database_owner`, not the app role. Asserting on the owner name would
    # fail on a correctly provisioned database.
    print("\nCREATE on schema public (what migrations actually need):")
    for dbname in databases:
        try:
            row = run_psql(
                f"SELECT has_schema_privilege('{role}', 'public', 'CREATE'), "
                "pg_catalog.pg_get_userbyid(nspowner) "
                "FROM pg_namespace WHERE nspname = 'public';",
                env,
                dbname=dbname,
                quiet=True,
            )
            granted, _, owner = row.partition("|")
            print(f"  {dbname}: create={granted} schema_owner={owner}")
            if granted != "t":
                print(f"    WARNING: {role} cannot create objects in {dbname}.public")
                print("    Migrations will fail with 'permission denied for schema public'.")
                ok = False
        except ProvisionError as exc:
            print(f"  {dbname}: unreachable — {exc}")
            ok = False

    print("\n" + ("VERIFY OK" if ok else "VERIFY FAILED"))
    return 0 if ok else 1


def cmd_rollback(args: argparse.Namespace, env: dict[str, str]) -> int:
    """Destructive. Requires the operator to retype the project name."""
    role = require_identifier(args.name, "role name")
    databases = [role] + ([f"{role}_directus"] if args.with_directus else [])

    print("This will PERMANENTLY DELETE:")
    for dbname in databases:
        print(f"  database {dbname}")
    print(f"  role     {role}")
    confirmation = input(f"\nType {role!r} to confirm: ").strip()
    if confirmation != role:
        print("Aborted — confirmation did not match.")
        return 1

    for dbname in databases:
        print(f"-> dropping database {dbname} ...", end=" ", flush=True)
        run_psql(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE);", env, quiet=True)
        print("ok")

    # A role cannot be dropped while it still owns objects anywhere. The
    # databases are gone, so only cluster-wide grants can remain.
    print(f"-> dropping role {role} ...", end=" ", flush=True)
    run_psql(f"DROP ROLE IF EXISTS {role};", env, quiet=True)
    print("ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env.deploy", help="operator inputs")
    parser.add_argument("--name", required=True, help="project slug -> role and database name")
    parser.add_argument(
        "--with-directus",
        action="store_true",
        help="also provision <name>_directus for the admin console",
    )
    parser.add_argument("--output", default=".env.deploy.generated")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print SQL, change nothing")
    mode.add_argument("--verify", action="store_true", help="check what exists")
    mode.add_argument("--rollback", action="store_true", help="DESTRUCTIVE: drop it all")
    args = parser.parse_args()

    try:
        env = load_env_file(Path(args.env_file))
        if args.verify:
            return cmd_verify(args, env)
        if args.rollback:
            return cmd_rollback(args, env)
        return cmd_provision(args, env)
    except ProvisionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

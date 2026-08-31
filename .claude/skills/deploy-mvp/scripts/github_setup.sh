#!/usr/bin/env bash
# Configure the GitHub Actions variables and secrets the deploy workflows read.
#
# Runs between "the Portainer stack exists" and "trust CI to deploy". Creates
# the deployment environment if absent, then sets every `vars.*` and `secrets.*`
# name that .github/workflows/*.yml references.
#
# Values come from a dotenv file; nothing is ever passed on the command line,
# where it would land in shell history and process listings.
#
# Usage:
#   github_setup.sh --env-file .env.deploy --environment Production --dry-run
#   github_setup.sh --env-file .env.deploy --environment Production
#   github_setup.sh --env-file .env.deploy --environment Production --audit
#
# Requires: gh (authenticated with repo admin), and a checkout of the repo.

set -o errexit
set -o nounset
set -o pipefail

ENV_FILE=".env.deploy"
ENVIRONMENT=""
MODE="apply"
REPO=""
# Audit only the workflows that actually deploy. A repo often carries release,
# promotion or notification workflows whose variables have nothing to do with
# deployment; auditing those turns a useful check into noise.
WORKFLOWS="build_backend.yml build_frontend.yml rollback.yml"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)    ENV_FILE="$2"; shift 2 ;;
        --environment) ENVIRONMENT="$2"; shift 2 ;;
        --repo)        REPO="$2"; shift 2 ;;
        --workflows)   WORKFLOWS="$2"; shift 2 ;;
        --all-workflows) WORKFLOWS=""; shift ;;
        --dry-run)     MODE="dry-run"; shift ;;
        --audit)       MODE="audit"; shift ;;
        -h|--help)     sed -n '2,22p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

# ── Variables (non-sensitive; readable back in plaintext via `gh variable list`)
VARS=(
    ADMIN_DB_DATABASE
    ADMIN_DB_HOST
    ADMIN_DB_USER
    ADMIN_EMAIL
    ADMIN_PUBLIC_URL

    BACKEND_DEPLOYMENT_COMPOSE_FILE
    BACKEND_DEPLOYMENT_SERVICE
    BACKEND_ECR_REPOSITORY_URI
    BACKEND_PROJECT_ID
    BACKEND_REPOSITORY_URI

    FRONTEND_DEPLOYMENT_COMPOSE_FILE
    FRONTEND_DEPLOYMENT_SERVICE
    FRONTEND_PROJECT_ID
    FRONTEND_REPOSITORY_URI

    INFISICAL_API_URL
    INFISICAL_SECRET_ENV

    PORTAINER_URL
)

# ── Secrets (encrypted; never readable back)
SECRETS=(
    ADMIN_DB_PASSWORD
    ADMIN_PASSWORD
    ADMIN_SECRET

    CF_ACCESS_CLIENT_ID
    CF_ACCESS_CLIENT_SECRET

    INFISICAL_MACHINE_CLIENT_ID
    INFISICAL_MACHINE_CLIENT_SECRET
    PORTAINER_TOKEN
)

die() { echo "error: $*" >&2; exit 1; }

command -v gh >/dev/null || die "gh CLI not found. Install it and run 'gh auth login'."
gh auth status >/dev/null 2>&1 || die "gh is not authenticated. Run 'gh auth login'."
[[ -f "$ENV_FILE" ]] || die "env file not found: $ENV_FILE"

REPO_ARGS=()
[[ -n "$REPO" ]] && REPO_ARGS=(--repo "$REPO")
REPO_SLUG="$(gh repo view "${REPO_ARGS[@]}" --json nameWithOwner --jq .nameWithOwner)"

# Read a key from the dotenv file without sourcing it (sourcing would execute
# any command substitution an operator accidentally pasted in).
#
# Uses `grep -E` and bash parameter expansion rather than a sed script: `\+`
# and `\?` are GNU extensions that BSD sed (macOS) treats as literal characters,
# which made every lookup silently return empty.
read_value() {
    local key="$1" line value
    line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" "$ENV_FILE" 2>/dev/null | head -n1)
    [[ -z "$line" ]] && return 0

    # Everything after the FIRST '=' — values may legitimately contain '='.
    value="${line#*=}"
    # Drop a trailing inline comment, but only when whitespace-separated so a
    # value containing '#' survives.
    value="$(printf '%s' "$value" | sed -e 's/[[:space:]][[:space:]]*#.*$//')"
    # Trim surrounding whitespace.
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    # Strip one matched pair of surrounding quotes.
    if [[ ${#value} -ge 2 && ${value:0:1} == '"' && ${value: -1} == '"' ]]; then
        value="${value:1:${#value}-2}"
    elif [[ ${#value} -ge 2 && ${value:0:1} == "'" && ${value: -1} == "'" ]]; then
        value="${value:1:${#value}-2}"
    fi
    printf '%s' "$value"
}

# ── Audit mode: every vars.*/secrets.* the workflows reference must be set ───
if [[ "$MODE" == "audit" ]]; then
    [[ -n "$ENVIRONMENT" ]] || die "--audit needs --environment"
    # Resolve which workflow files to scan.
    files=()
    if [[ -n "$WORKFLOWS" ]]; then
        for name in $WORKFLOWS; do
            [[ -f ".github/workflows/$name" ]] && files+=(".github/workflows/$name")
        done
        if [[ ${#files[@]} -eq 0 ]]; then
            die "none of the expected deploy workflows exist: $WORKFLOWS
Pass --workflows '<names>' or --all-workflows to scan everything."
        fi
    else
        while IFS= read -r path; do files+=("$path"); done \
            < <(find .github/workflows -name '*.yml' -o -name '*.yaml' | sort)
    fi

    echo "Auditing $REPO_SLUG environment '$ENVIRONMENT'"
    echo "Workflows:   ${files[*]#.github/workflows/}"
    echo

    referenced_vars=$(grep -rhoE '\$\{\{[[:space:]]*vars\.[A-Z0-9_]+' "${files[@]}" 2>/dev/null \
        | grep -oE '[A-Z0-9_]+$' | sort -u || true)
    referenced_secrets=$(grep -rhoE '\$\{\{[[:space:]]*secrets\.[A-Z0-9_]+' "${files[@]}" 2>/dev/null \
        | grep -oE '[A-Z0-9_]+$' | sort -u || true)

    set_vars=$(gh variable list "${REPO_ARGS[@]}" --env "$ENVIRONMENT" --json name --jq '.[].name' 2>/dev/null | sort -u || true)
    set_vars_repo=$(gh variable list "${REPO_ARGS[@]}" --json name --jq '.[].name' 2>/dev/null | sort -u || true)
    set_secrets=$(gh secret list "${REPO_ARGS[@]}" --env "$ENVIRONMENT" --json name --jq '.[].name' 2>/dev/null | sort -u || true)
    set_secrets_repo=$(gh secret list "${REPO_ARGS[@]}" --json name --jq '.[].name' 2>/dev/null | sort -u || true)

    all_vars=$(printf '%s\n%s\n' "$set_vars" "$set_vars_repo" | sort -u)
    all_secrets=$(printf '%s\n%s\n' "$set_secrets" "$set_secrets_repo" | sort -u)

    missing=0
    for name in $referenced_vars; do
        if grep -qx "$name" <<<"$all_vars"; then
            echo "  [ok]   vars.$name"
        else
            echo "  [MISS] vars.$name"
            missing=$((missing + 1))
        fi
    done
    for name in $referenced_secrets; do
        # GITHUB_TOKEN is injected by Actions; it is never configured by hand.
        [[ "$name" == "GITHUB_TOKEN" ]] && { echo "  [ok]   secrets.GITHUB_TOKEN (automatic)"; continue; }
        if grep -qx "$name" <<<"$all_secrets"; then
            echo "  [ok]   secrets.$name"
        else
            echo "  [MISS] secrets.$name"
            missing=$((missing + 1))
        fi
    done

    # Names this script would set that no scanned workflow reads. Usually a
    # leftover from an earlier deployment topology (e.g. an ECR-era URI kept
    # after the move to ghcr.io). Harmless, but worth knowing it does nothing.
    unreferenced=""
    for name in "${VARS[@]}"; do
        grep -qx "$name" <<<"$referenced_vars" || unreferenced+="  vars.$name"$'\n'
    done
    for name in "${SECRETS[@]}"; do
        grep -qx "$name" <<<"$referenced_secrets" || unreferenced+="  secrets.$name"$'\n'
    done
    if [[ -n "$unreferenced" ]]; then
        echo
        echo "Configured by this script but read by no scanned workflow:"
        printf '%s' "$unreferenced"
        echo "Setting them is harmless; they simply have no effect here."
    fi

    echo
    if [[ "$missing" -gt 0 ]]; then
        echo "$missing referenced name(s) are NOT configured."
        echo
        echo "An unset vars.* expands to an EMPTY STRING in Actions — the deploy"
        echo "step then targets a stack name of '' and reports success while"
        echo "having changed nothing. Fix these before trusting CI."
        exit 1
    fi
    echo "All referenced variables and secrets are configured."
    exit 0
fi

# ── Apply / dry-run ─────────────────────────────────────────────────────────
[[ -n "$ENVIRONMENT" ]] || die "--environment is required (e.g. Production or Development)"

echo "Repository:  $REPO_SLUG"
echo "Environment: $ENVIRONMENT"
echo "Source:      $ENV_FILE"
echo "Mode:        $MODE"
echo

# The environment must exist before `gh secret set --env` will work; that call
# 404s otherwise. This endpoint is create-or-update, so it is safe to re-run.
if gh api "repos/$REPO_SLUG/environments/$ENVIRONMENT" >/dev/null 2>&1; then
    echo "Environment '$ENVIRONMENT' already exists."
else
    if [[ "$MODE" == "dry-run" ]]; then
        echo "would create environment '$ENVIRONMENT'"
    else
        gh api --method PUT "repos/$REPO_SLUG/environments/$ENVIRONMENT" --input /dev/null >/dev/null
        echo "Created environment '$ENVIRONMENT'."
    fi
fi
echo

set_one() {
    local kind="$1" name="$2" value="$3"
    if [[ -z "$value" ]]; then
        printf '  %-34s SKIP (no value in env file)\n' "$name"
        return 1
    fi
    if [[ "$MODE" == "dry-run" ]]; then
        if [[ "$kind" == "secret" ]]; then
            printf '  %-34s would set (%d chars)\n' "$name" "${#value}"
        else
            printf '  %-34s would set = %s\n' "$name" "$value"
        fi
        return 0
    fi
    # --body keeps the value off argv? No: it is an argument. Pipe via stdin so
    # the value never appears in the process table.
    if [[ "$kind" == "secret" ]]; then
        printf '%s' "$value" | gh secret set "$name" "${REPO_ARGS[@]}" --env "$ENVIRONMENT" >/dev/null
        printf '  %-34s set (%d chars)\n' "$name" "${#value}"
    else
        printf '%s' "$value" | gh variable set "$name" "${REPO_ARGS[@]}" --env "$ENVIRONMENT" >/dev/null
        printf '  %-34s set = %s\n' "$name" "$value"
    fi
}

skipped=0

echo "VARIABLES (values are readable back by anyone with repo access):"
for name in "${VARS[@]}"; do
    set_one variable "$name" "$(read_value "$name")" || skipped=$((skipped + 1))
done

echo
echo "SECRETS (encrypted; values never printed):"
for name in "${SECRETS[@]}"; do
    set_one secret "$name" "$(read_value "$name")" || skipped=$((skipped + 1))
done

echo
if [[ "$skipped" -gt 0 ]]; then
    echo "$skipped name(s) were skipped because $ENV_FILE has no value for them."
    echo "Add them and re-run — this script is idempotent."
fi

if [[ "$MODE" == "dry-run" ]]; then
    echo "Dry run only. Re-run without --dry-run to apply."
else
    echo "Done. Verify with:"
    echo "  $0 --env-file $ENV_FILE --environment $ENVIRONMENT --audit"
fi

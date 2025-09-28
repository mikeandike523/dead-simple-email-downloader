#!/usr/bin/env bash
set -euo pipefail

# schema-deploy.sh (Atlas edition, with Python3 urlencode, base URL + --schema)
#
# Uses a base MySQL connection URL (no trailing /DB) and binds the schema via
# --schema "${MYSQL_DATABASE}" for both diff and apply.

AUTO_APPROVE="false"
if [[ "${1:-}" == "-y" || "${1:-}" == "--yes" || "${1:-}" == "--auto-approve" ]]; then
  AUTO_APPROVE="true"
fi

# ---- Helpers ---------------------------------------------------------------

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

urlencode() {
  python -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$1"
}

# ---- Checks ----------------------------------------------------------------

need_cmd atlas
need_cmd docker
need_cmd python

[[ -f ".env" ]] || die "Missing .env in current directory"
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${MYSQL_HOST:?MYSQL_HOST not set in .env}"
: "${MYSQL_PORT:?MYSQL_PORT not set in .env}"
: "${MYSQL_USER:?MYSQL_USER not set in .env}"
: "${MYSQL_PASSWORD:?MYSQL_PASSWORD not set in .env}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE not set in .env}"

[[ -f "schema.sql" ]] || die "Missing schema.sql in current directory"

# Build a BASE URL (no database in the path) and bind the DB via --schema.
PW_ENC="$(urlencode "${MYSQL_PASSWORD}")"
MYSQL_URL_BASE="mysql://${MYSQL_USER}:${PW_ENC}@${MYSQL_HOST}:${MYSQL_PORT}"

DEV_URL="${ATLAS_DEV_URL:-docker://mysql/8}"

echo "==> Using dev-url: ${DEV_URL}"
echo "==> Target (base): ${MYSQL_URL_BASE}  (schema bound with --schema=${MYSQL_DATABASE})"
echo

# ---- Diff ------------------------------------------------------------------

set +e
DIFF_OUTPUT="$(atlas schema diff \
  --dev-url "${DEV_URL}" \
  --from "${MYSQL_URL_BASE}" \
  --to "file://schema.sql" \
  --schema "${MYSQL_DATABASE}" 2>&1)"
DIFF_EXIT=$?
set -e

echo "==> Diff (live -> schema.sql)"
echo
echo "${DIFF_OUTPUT}"
echo

if [[ $DIFF_EXIT -ne 0 ]]; then
  echo "atlas schema diff exited with code ${DIFF_EXIT}. Aborting."
  exit "$DIFF_EXIT"
fi

if echo "${DIFF_OUTPUT}" | grep -qE '^\s*-- No changes' && \
   ! echo "${DIFF_OUTPUT}" | grep -qE '^(CREATE|ALTER|DROP|TRUNCATE|RENAME)'; then
  echo "No differences found. Database is already in sync with schema.sql."
  exit 0
fi

# ---- Confirm apply ---------------------------------------------------------

if [[ "$AUTO_APPROVE" != "true" ]]; then
  read -r -p "Apply these changes to ${MYSQL_DATABASE}? [y/N]: " ANSWER
  ANSWER="${ANSWER,,}"
  if [[ "$ANSWER" != "y" && "$ANSWER" != "yes" ]]; then
    echo "Aborted. No changes applied."
    exit 0
  fi
else
  echo "Auto-approve enabled (-y). Proceeding to plan & apply."
fi

# ---- Safety check (dry-run) ------------------------------------------------
echo
echo "==> Planning apply (dry-run) to check for destructive changes..."
set +e
PLAN_OUTPUT="$(atlas schema apply \
  --dev-url "${DEV_URL}" \
  --url "${MYSQL_URL_BASE}" \
  --to "file://schema.sql" \
  --schema "${MYSQL_DATABASE}" \
  --dry-run 2>&1)"
PLAN_EXIT=$?
set -e

echo "${PLAN_OUTPUT}"
echo

if [[ $PLAN_EXIT -ne 0 ]]; then
  echo "atlas schema apply (dry-run) failed with exit ${PLAN_EXIT}. Aborting."
  exit "$PLAN_EXIT"
fi

if echo "${PLAN_OUTPUT}" | grep -qiE '\bDROP\b|\bTRUNCATE\b|\bALTER\b.+\bDROP\b|\bRENAME COLUMN\b'; then
  echo "Detected potentially destructive changes."
  if [[ "$AUTO_APPROVE" != "true" ]]; then
    read -r -p "Proceed with destructive changes? [y/N]: " ALLOW
    ALLOW="${ALLOW,,}"
    if [[ "$ALLOW" != "y" && "$ALLOW" != "yes" ]]; then
      echo "Aborted. No destructive changes applied."
      exit 1
    fi
  else
    echo "Auto-approve enabled; proceeding despite destructive changes."
  fi
fi

# ---- Apply -----------------------------------------------------------------

echo
echo "==> Applying changes with atlas schema apply"
APPLY_ARGS=(
  atlas schema apply
  --dev-url "${DEV_URL}"
  --url "${MYSQL_URL_BASE}"
  --to "file://schema.sql"
  --auto-approve # Since already hit y on bash-side at this point
)

# if [[ "$AUTO_APPROVE" == "true" ]]; then
  # APPLY_ARGS+=(--auto-approve)
# fi

set +e
APPLY_OUTPUT="$("${APPLY_ARGS[@]}" 2>&1)"
APPLY_EXIT=$?
set -e

echo "${APPLY_OUTPUT}"
echo

if [[ $APPLY_EXIT -eq 0 ]]; then
  echo "Apply complete."
  exit 0
else
  echo "Apply failed (exit ${APPLY_EXIT}). See output above."
  exit "$APPLY_EXIT"
fi

#!/usr/bin/env bash
# Usage: ./read_env_redacted.sh [path/to/.env]
# Prints variable names with redacted values. Skips comments and blank lines.

FILE="${1:-.env}"

if [[ ! -f "$FILE" ]]; then
  echo "File not found: $FILE" >&2
  exit 1
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip blank lines and comments
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && echo "$line" && continue
  # Redact value, keep name
  echo "${line%%=*}=***"
done < "$FILE"

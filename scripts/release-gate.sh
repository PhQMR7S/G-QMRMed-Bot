#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'RELEASE GATE FAILED: %s\n' "$1" >&2
  exit 1
}

require_env() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "$name is required"
}

require_env APP_ENV
[[ "$APP_ENV" == "production" ]] || fail "APP_ENV must be production"
require_env DATABASE_URL
require_env REDIS_URL
require_env TELEGRAM_BOT_TOKEN
require_env ADMIN_SECRET
require_env COMFYUI_BASE_URL
require_env COMFYUI_WORKFLOW_JSON

(( ${#ADMIN_SECRET} >= 32 )) || fail "ADMIN_SECRET must contain at least 32 characters"

python - <<'PY'
import json
import os

workflow = os.environ["COMFYUI_WORKFLOW_JSON"]
try:
    value = json.loads(workflow)
except json.JSONDecodeError as exc:
    raise SystemExit(f"COMFYUI_WORKFLOW_JSON is not valid JSON: {exc}")
if not isinstance(value, dict) or not value:
    raise SystemExit("COMFYUI_WORKFLOW_JSON must be a non-empty JSON object")
PY

provider_order="${AI_PROVIDER_ORDER:-ollama,openrouter_free,groq_free,openai_compatible,openai}"
IFS=',' read -r -a providers <<< "$provider_order"
configured=0
for provider in "${providers[@]}"; do
  case "$provider" in
    ollama)
      [[ -n "${OLLAMA_BASE_URL:-}" ]] && configured=1
      ;;
    openrouter_free)
      [[ -n "${OPENROUTER_API_KEY:-}" ]] && configured=1
      ;;
    groq_free)
      [[ -n "${GROQ_API_KEY:-}" ]] && configured=1
      ;;
    openai_compatible)
      [[ -n "${AI_COMPATIBLE_API_KEY:-}" && -n "${AI_COMPATIBLE_BASE_URL:-}" ]] && configured=1
      ;;
    openai)
      if [[ "${AI_ALLOW_PAID:-false}" == "true" ]]; then
        [[ -n "${AI_API_KEY:-}" && -n "${AI_BASE_URL:-}" ]] && configured=1
      fi
      ;;
  esac
done
(( configured == 1 )) || fail "no usable AI provider is configured in AI_PROVIDER_ORDER"

s3_values=(S3_ENDPOINT S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_BUCKET S3_REGION)
s3_set=0
s3_missing=0
for name in "${s3_values[@]}"; do
  if [[ -n "${!name:-}" ]]; then
    ((s3_set+=1))
  else
    ((s3_missing+=1))
  fi
done
(( s3_set == 0 || s3_set == ${#s3_values[@]} )) || fail "S3 configuration must be complete or entirely omitted"

drive_credentials_set=0
drive_folder_set=0
[[ -n "${GOOGLE_DRIVE_CREDENTIALS_JSON:-}" ]] && drive_credentials_set=1
[[ -n "${GOOGLE_DRIVE_FOLDER_ID:-}" ]] && drive_folder_set=1
(( drive_credentials_set == drive_folder_set )) || fail "Google Drive credentials and folder ID must be configured together"
if (( drive_credentials_set == 1 )); then
  (( s3_set == 0 )) || fail "S3 and Google Drive result storage cannot be enabled together"
  python - <<'PY'
import json
import os

try:
    value = json.loads(os.environ["GOOGLE_DRIVE_CREDENTIALS_JSON"])
except json.JSONDecodeError as exc:
    raise SystemExit(f"GOOGLE_DRIVE_CREDENTIALS_JSON is not valid JSON: {exc}")
if not isinstance(value, dict) or not value:
    raise SystemExit("GOOGLE_DRIVE_CREDENTIALS_JSON must be a non-empty JSON object")
required = {"client_email", "private_key", "token_uri"}
missing = sorted(required - value.keys())
if missing:
    raise SystemExit("GOOGLE_DRIVE_CREDENTIALS_JSON is missing required service-account fields")
PY
fi

printf '%s\n' "Production release gate: configuration contract passed"
printf '%s\n' "Credentials were validated without printing their values"

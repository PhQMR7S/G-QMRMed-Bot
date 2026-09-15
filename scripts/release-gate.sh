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

(( ${#ADMIN_SECRET} >= 32 )) || fail "ADMIN_SECRET must contain at least 32 characters"

provider_order="${AI_PROVIDER_ORDER:-ollama,openrouter_free,groq_free,openai_compatible,openai}"
IFS=',' read -r -a providers <<< "$provider_order"
configured=0
for provider in "${providers[@]}"; do
  provider="${provider// /}"
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
      [[ -n "${AI_COMPATIBLE_API_KEY:-}" && -n "${AI_COMPATIBLE_BASE_URL:-}" && -n "${AI_COMPATIBLE_MODEL:-}" ]] && configured=1
      ;;
    openai)
      if [[ "${AI_ALLOW_PAID:-false}" == "true" ]]; then
        [[ -n "${AI_API_KEY:-}" && -n "${AI_BASE_URL:-}" && -n "${AI_MODEL:-}" ]] && configured=1
      fi
      ;;
  esac
done
(( configured == 1 )) || fail "no usable AI synthesis provider is configured in AI_PROVIDER_ORDER"

image_order="${IMAGE_PROVIDER_ORDER:-openai,procedural}"
IFS=',' read -r -a image_providers <<< "$image_order"
image_configured=0
image_fallback=0
for provider in "${image_providers[@]}"; do
  provider="${provider// /}"
  case "$provider" in
    openai)
      [[ -n "${AI_API_KEY:-}" && -n "${OPENAI_IMAGE_MODEL:-}" ]] && image_configured=1
      ;;
    huggingface)
      [[ -n "${HUGGINGFACE_TOKEN:-}" && -n "${HUGGINGFACE_IMAGE_MODEL:-}" ]] && image_configured=1
      ;;
    comfyui)
      [[ -n "${COMFYUI_BASE_URL:-}" && -n "${COMFYUI_WORKFLOW_JSON:-}" ]] || fail "ComfyUI is selected in IMAGE_PROVIDER_ORDER but its configuration is incomplete"
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
      image_configured=1
      ;;
    procedural)
      image_fallback=1
      ;;
  esac
done
(( image_configured == 1 || image_fallback == 1 )) || fail "no usable image provider is configured in IMAGE_PROVIDER_ORDER"

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

printf '%s\n' "Production release gate: configuration contract passed"
printf '%s\n' "Credentials were validated without printing their values"

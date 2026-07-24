#!/usr/bin/env bash
# =============================================================================
# setup_cloudflare_terraform.sh — CloudBooter Cloudflare Provisioner
# =============================================================================
# Free-plan Workers / KV / R2 / D1 bootstrap. Mirrors GCP/OCI workflow shape.
#
# Usage:
#   ./setup_cloudflare_terraform.sh
#   NON_INTERACTIVE=true CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... \
#     ./setup_cloudflare_terraform.sh
#
# Environment variables:
#   CLOUDFLARE_API_TOKEN          — API token (required non-interactive)
#   CLOUDFLARE_ACCOUNT_ID         — Account ID (required)
#   CLOUDFLARE_ZONE_ID            — Optional zone ID
#   CLOUDFLARE_ZONE_NAME          — Optional zone name
#   CLOUDFLARE_WORKER_NAME        — Worker name (default: cloudbooter-worker)
#   CLOUDFLARE_R2_BUCKET          — R2 bucket name (default: cloudbooter-r2)
#   CLOUDFLARE_D1_NAME            — D1 database name (default: cloudbooter-db)
#   CLOUDFLARE_KV_TITLE           — KV namespace title (default: cloudbooter-kv)
#   CLOUDFLARE_ALLOW_PAID_RESOURCES — Skip free-tier guards when "true"
#   CF_MODE                       — wrangler | npx | api
#   NON_INTERACTIVE, AUTO_DEPLOY, AUTO_USE_EXISTING, SKIP_CONFIG, DEBUG,
#   FORCE_REAUTH, RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY
# =============================================================================
set -euo pipefail

[[ "${DEBUG:-false}" == "true" ]] && set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# =============================================================================
# Free-Tier Constants (sync with free_tier.py + Terraform check blocks)
# Verified 2026-07-24: developers.cloudflare.com Workers/R2/D1/KV/DO/Pages/AI
# =============================================================================
readonly CF_FREE_WORKERS_REQUESTS_PER_DAY=100000
readonly CF_FREE_WORKERS_CPU_MS=10
readonly CF_FREE_WORKERS_COUNT=100
readonly CF_FREE_KV_READS_PER_DAY=100000
readonly CF_FREE_KV_WRITES_PER_DAY=1000
readonly CF_FREE_KV_STORAGE_GB=1
readonly CF_FREE_R2_STORAGE_GB=10
readonly CF_FREE_R2_CLASS_A_OPS=1000000
readonly CF_FREE_R2_CLASS_B_OPS=10000000
readonly CF_FREE_D1_ROWS_READ_PER_DAY=5000000
readonly CF_FREE_D1_ROWS_WRITTEN_PER_DAY=100000
readonly CF_FREE_D1_STORAGE_GB=5
readonly CF_FREE_DO_REQUESTS_PER_DAY=100000
readonly CF_FREE_QUEUES_OPS_PER_DAY=10000
readonly CF_FREE_PAGES_BUILDS_PER_MONTH=500
readonly CF_FREE_WORKERS_AI_NEURONS_PER_DAY=10000

readonly DEFAULT_WORKER_NAME="cloudbooter-worker"
readonly DEFAULT_R2_BUCKET="cloudbooter-r2"
readonly DEFAULT_D1_NAME="cloudbooter-db"
readonly DEFAULT_KV_TITLE="cloudbooter-kv"

RETRY_MAX_ATTEMPTS="${RETRY_MAX_ATTEMPTS:-8}"
RETRY_BASE_DELAY="${RETRY_BASE_DELAY:-15}"

readonly -a CF_RETRY_PATTERNS=(
  "rate limited"
  "Error 429"
  "429 Too Many Requests"
  "Error 503"
  "temporarily unavailable"
  "timeout"
)

# State
account_id="${CLOUDFLARE_ACCOUNT_ID:-}"
api_token="${CLOUDFLARE_API_TOKEN:-}"
worker_name="${CLOUDFLARE_WORKER_NAME:-${DEFAULT_WORKER_NAME}}"
r2_bucket="${CLOUDFLARE_R2_BUCKET:-${DEFAULT_R2_BUCKET}}"
d1_name="${CLOUDFLARE_D1_NAME:-${DEFAULT_D1_NAME}}"
kv_title="${CLOUDFLARE_KV_TITLE:-${DEFAULT_KV_TITLE}}"
cf_mode="${CF_MODE:-}"
workers_cpu_ms="${CLOUDFLARE_WORKERS_CPU_MS:-10}"

RESET="\033[0m"; BLUE="\033[34m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; BOLD="\033[1m"
print_status()  { echo -e "${BLUE}[INFO]${RESET}  $*"; }
print_success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
print_warning() { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
print_error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
print_header()  { echo -e "\n${BOLD}=== $* ===${RESET}\n"; }

command_exists() { command -v "$1" &>/dev/null; }

prompt_with_default() {
  local prompt="$1" default="$2" result
  if [[ "${NON_INTERACTIVE:-false}" == "true" ]]; then
    echo "${default}"
    return
  fi
  read -r -p "${prompt} [${default}]: " result || true
  echo "${result:-${default}}"
}

# =============================================================================
# Prerequisites
# =============================================================================
detect_cf_mode() {
  if [[ -n "${cf_mode}" ]]; then
    return
  fi
  if command_exists wrangler; then
    cf_mode="wrangler"
  elif command_exists npx; then
    cf_mode="npx"
  else
    cf_mode="api"
  fi
  export CF_MODE="${cf_mode}"
  print_status "CF_MODE=${cf_mode}"
}

ensure_python() {
  if ! command_exists python3; then
    print_error "python3 is required"
    exit 1
  fi
  if [[ -f requirements.txt ]]; then
    python3 -m pip install -q -r requirements.txt 2>/dev/null || \
      python3 -m pip install -q --user -r requirements.txt
  fi
  export PYTHONPATH="${SCRIPT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
}

# =============================================================================
# Auth
# =============================================================================
resolve_auth() {
  print_header "Authentication"
  if [[ -z "${api_token}" && -n "${CLOUDFLARE_API_TOKEN_FILE:-}" && -f "${CLOUDFLARE_API_TOKEN_FILE}" ]]; then
    api_token="$(tr -d '\r\n' < "${CLOUDFLARE_API_TOKEN_FILE}")"
    export CLOUDFLARE_API_TOKEN="${api_token}"
  fi

  if [[ -z "${account_id}" ]]; then
    account_id="$(prompt_with_default "Cloudflare Account ID" "")"
  fi
  if [[ -z "${account_id}" ]]; then
    print_error "CLOUDFLARE_ACCOUNT_ID is required"
    exit 1
  fi
  export CLOUDFLARE_ACCOUNT_ID="${account_id}"

  if [[ -z "${api_token}" ]]; then
    if [[ "${NON_INTERACTIVE:-false}" == "true" ]]; then
      print_error "NON_INTERACTIVE requires CLOUDFLARE_API_TOKEN"
      exit 1
    fi
    if [[ "${cf_mode}" == "wrangler" || "${cf_mode}" == "npx" ]]; then
      print_status "Opening wrangler login…"
      if [[ "${cf_mode}" == "wrangler" ]]; then
        wrangler login || true
      else
        npx --yes wrangler login || true
      fi
    fi
    api_token="$(prompt_with_default "Cloudflare API Token" "")"
  fi

  if [[ -z "${api_token}" ]]; then
    print_error "No API token available"
    exit 1
  fi
  export CLOUDFLARE_API_TOKEN="${api_token}"
  print_success "Auth context ready (account=${account_id})"
}

# =============================================================================
# Free-tier validate
# =============================================================================
validate_free_tier() {
  print_header "Free-tier validation"
  if [[ "${CLOUDFLARE_ALLOW_PAID_RESOURCES:-false}" == "true" ]]; then
    print_warning "CLOUDFLARE_ALLOW_PAID_RESOURCES=true — guards relaxed"
    return
  fi
  if (( workers_cpu_ms > CF_FREE_WORKERS_CPU_MS )); then
    print_error "Workers CPU ${workers_cpu_ms} ms exceeds Free plan (${CF_FREE_WORKERS_CPU_MS} ms)"
    exit 1
  fi
  print_success "Within Free plan CPU / storage-class defaults"
}

# =============================================================================
# Generate + optional apply
# =============================================================================
generate_terraform() {
  print_header "Generate Terraform"
  local out_dir="${TF_OUTPUT_DIR:-.}"
  python3 -m cloudbooter.cli deploy \
    --account-id "${account_id}" \
    --api-token "${api_token}" \
    --worker-name "${worker_name}" \
    --r2-bucket "${r2_bucket}" \
    --d1-name "${d1_name}" \
    --kv-title "${kv_title}" \
    --workers-cpu-ms "${workers_cpu_ms}" \
    --output-dir "${out_dir}" \
    --no-auto-deploy \
    --non-interactive
  print_success "Terraform written to ${out_dir}"
}

terraform_apply_with_retry() {
  print_header "Terraform apply"
  local attempt=1 delay="${RETRY_BASE_DELAY}"
  export TF_VAR_cloudflare_api_token="${api_token}"
  terraform init -input=false
  terraform plan -input=false -out=tfplan
  while (( attempt <= RETRY_MAX_ATTEMPTS )); do
    if terraform apply -input=false tfplan; then
      print_success "Apply succeeded"
      return 0
    fi
    print_warning "Apply failed (attempt ${attempt}/${RETRY_MAX_ATTEMPTS}); retrying in ${delay}s…"
    sleep "${delay}"
    delay=$(( delay * 2 ))
    attempt=$(( attempt + 1 ))
    terraform plan -input=false -out=tfplan || true
  done
  print_error "Apply failed after ${RETRY_MAX_ATTEMPTS} attempts"
  return 1
}

# =============================================================================
# Main
# =============================================================================
main() {
  print_header "CloudBooter Cloudflare"
  detect_cf_mode
  ensure_python
  resolve_auth
  validate_free_tier

  if [[ "${SKIP_CONFIG:-false}" != "true" ]]; then
    worker_name="$(prompt_with_default "Worker name" "${worker_name}")"
    r2_bucket="$(prompt_with_default "R2 bucket name" "${r2_bucket}")"
    d1_name="$(prompt_with_default "D1 database name" "${d1_name}")"
  fi

  generate_terraform

  if [[ "${AUTO_DEPLOY:-false}" == "true" ]]; then
    if ! command_exists terraform; then
      print_error "terraform not found; install or run: python3 -m cloudbooter.cli install-deps"
      exit 1
    fi
    terraform_apply_with_retry
  else
    print_status "Skipping apply (set AUTO_DEPLOY=true to apply). Review .tf files first."
  fi

  print_success "Done."
}

main "$@"

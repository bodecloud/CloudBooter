#!/usr/bin/env bash

# Helper: Retry Terraform apply on transient 'Out of Capacity' errors
# Usage:
#   ./helper_scripts/out_of_capacity.sh [--max-attempts N] [--base-delay S] [--plan tfplan]
#
# If a plan file is present (default: ./tfplan) it will run `terraform apply <plan>`.
# Otherwise it will run `terraform apply -auto-approve`.
#
# Behavior:
#  - Detects "Out of Capacity" / "OutOfHostCapacity" errors and retries with exponential backoff
#  - Stops immediately on non-retryable terraform errors
#  - Writes output to ./out_of_capacity.log

set -euo pipefail

MAX_ATTEMPTS=8
BASE_DELAY=15
PLAN_FILE="tfplan"
LOGFILE="${LOGFILE:-out_of_capacity.log}"

# Parse args
while [ "$#" -gt 0 ]; do
  case "$1" in
    --max-attempts|--base-delay|--plan)
      if [ "$#" -lt 2 ] || [[ "$2" == --* ]]; then
        echo "Missing value for $1" >&2
        exit 2
      fi ;;
  esac
  case "$1" in
    --max-attempts)
      MAX_ATTEMPTS="$2"; shift 2 ;;
    --base-delay)
      BASE_DELAY="$2"; shift 2 ;;
    --plan)
      PLAN_FILE="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,120p' "$0"
      exit 0 ;;
    *)
      echo "Unknown arg: $1"; exit 2 ;;
  esac
done

if ! [[ "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ && "$BASE_DELAY" =~ ^[0-9]+$ ]]; then
  echo "Attempts must be positive and delay must be non-negative integers" >&2
  exit 2
fi
mkdir -p -- "$(dirname -- "$LOGFILE")"

echo "[INFO] Out-of-capacity auto-apply helper" | tee -a "$LOGFILE"
echo "[INFO] Max attempts=$MAX_ATTEMPTS, base delay=${BASE_DELAY}s, plan=${PLAN_FILE}" | tee -a "$LOGFILE"

attempt=1
while [ $attempt -le $MAX_ATTEMPTS ]; do
  echo "[INFO] Attempt $attempt/$MAX_ATTEMPTS" | tee -a "$LOGFILE"

  if [ -f "$PLAN_FILE" ]; then
    if [ "$attempt" -gt 1 ]; then
      echo "[INFO] Refreshing plan after previous partial apply" | tee -a "$LOGFILE"
      terraform plan -input=false -out="$PLAN_FILE" 2>&1 | tee -a "$LOGFILE"
    fi
    echo "[INFO] Applying plan file: $PLAN_FILE" | tee -a "$LOGFILE"
    out=$(terraform apply -input=false "$PLAN_FILE" 2>&1) && rc=0 || rc=$?
  else
    echo "[INFO] Applying with -auto-approve" | tee -a "$LOGFILE"
    out=$(terraform apply -input=false -auto-approve 2>&1) && rc=0 || rc=$?
  fi

  echo "$out" | tee -a "$LOGFILE"

  if [ $rc -eq 0 ]; then
    echo "[SUCCESS] terraform apply succeeded" | tee -a "$LOGFILE"
    exit 0
  fi

  if echo "$out" | grep -i -E "out of capacity|out of host capacity|OutOfCapacity|OutOfHostCapacity" >/dev/null 2>&1; then
    echo "[WARN] Detected Out of Capacity; will retry" | tee -a "$LOGFILE"
  else
    echo "[ERROR] terraform apply failed with non-retryable error (exit $rc)" | tee -a "$LOGFILE"
    exit $rc
  fi

  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    break
  fi
  sleep_time=$(( BASE_DELAY * (2 ** (attempt - 1)) ))
  echo "[INFO] Sleeping ${sleep_time}s before retry" | tee -a "$LOGFILE"
  sleep $sleep_time
  attempt=$((attempt + 1))
done

echo "[ERROR] Exhausted $MAX_ATTEMPTS attempts without success" | tee -a "$LOGFILE"
exit 1

#Requires -Version 5.1
<#
.SYNOPSIS
  CloudBooter Cloudflare Free-plan provisioner (PowerShell).

.DESCRIPTION
  Mirrors setup_cloudflare_terraform.sh for Windows.

.EXAMPLE
  $env:CLOUDFLARE_API_TOKEN = "..."
  $env:CLOUDFLARE_ACCOUNT_ID = "..."
  $env:NON_INTERACTIVE = "true"
  .\setup_cloudflare_terraform.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Free-tier constants (sync with free_tier.py) — verified 2026-07-24
$script:CF_FREE_WORKERS_CPU_MS = 10
$script:DEFAULT_WORKER_NAME = "cloudbooter-worker"
$script:DEFAULT_R2_BUCKET = "cloudbooter-r2"
$script:DEFAULT_D1_NAME = "cloudbooter-db"
$script:DEFAULT_KV_TITLE = "cloudbooter-kv"

function Write-Info([string]$Message) { Write-Host "[INFO]  $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message)   { Write-Host "[OK]    $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "[WARN]  $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message)  { Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Get-PromptValue([string]$Prompt, [string]$Default) {
  if ($env:NON_INTERACTIVE -eq "true") { return $Default }
  $value = Read-Host "$Prompt [$Default]"
  if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
  return $value
}

function Ensure-PythonDeps {
  if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
    throw "Python 3 is required"
  }
  $py = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
  if (Test-Path ".\requirements.txt") {
    & $py -m pip install -q -r requirements.txt
  }
  $env:PYTHONPATH = (Join-Path $PSScriptRoot "src") + [IO.Path]::PathSeparator + $env:PYTHONPATH
  return $py
}

function Resolve-CfMode {
  if ($env:CF_MODE) { return $env:CF_MODE }
  if (Get-Command wrangler -ErrorAction SilentlyContinue) { return "wrangler" }
  if (Get-Command npx -ErrorAction SilentlyContinue) { return "npx" }
  return "api"
}

# --- Main ---
Write-Host "`n=== CloudBooter Cloudflare ===`n" -ForegroundColor White

$cfMode = Resolve-CfMode
$env:CF_MODE = $cfMode
Write-Info "CF_MODE=$cfMode"

$py = Ensure-PythonDeps

$accountId = if ($env:CLOUDFLARE_ACCOUNT_ID) { $env:CLOUDFLARE_ACCOUNT_ID } else { Get-PromptValue "Cloudflare Account ID" "" }
if ([string]::IsNullOrWhiteSpace($accountId)) { throw "CLOUDFLARE_ACCOUNT_ID is required" }
$env:CLOUDFLARE_ACCOUNT_ID = $accountId

$apiToken = $env:CLOUDFLARE_API_TOKEN
if (-not $apiToken -and $env:CLOUDFLARE_API_TOKEN_FILE -and (Test-Path $env:CLOUDFLARE_API_TOKEN_FILE)) {
  $apiToken = (Get-Content -Raw $env:CLOUDFLARE_API_TOKEN_FILE).Trim()
  $env:CLOUDFLARE_API_TOKEN = $apiToken
}
if (-not $apiToken) {
  if ($env:NON_INTERACTIVE -eq "true") { throw "NON_INTERACTIVE requires CLOUDFLARE_API_TOKEN" }
  $apiToken = Get-PromptValue "Cloudflare API Token" ""
  $env:CLOUDFLARE_API_TOKEN = $apiToken
}
if (-not $apiToken) { throw "No API token available" }

$cpuMs = if ($env:CLOUDFLARE_WORKERS_CPU_MS) { [int]$env:CLOUDFLARE_WORKERS_CPU_MS } else { 10 }
if ($env:CLOUDFLARE_ALLOW_PAID_RESOURCES -ne "true" -and $cpuMs -gt $script:CF_FREE_WORKERS_CPU_MS) {
  throw "Workers CPU $cpuMs ms exceeds Free plan ($script:CF_FREE_WORKERS_CPU_MS ms)"
}

$workerName = if ($env:CLOUDFLARE_WORKER_NAME) { $env:CLOUDFLARE_WORKER_NAME } else { $script:DEFAULT_WORKER_NAME }
$r2Bucket = if ($env:CLOUDFLARE_R2_BUCKET) { $env:CLOUDFLARE_R2_BUCKET } else { $script:DEFAULT_R2_BUCKET }
$d1Name = if ($env:CLOUDFLARE_D1_NAME) { $env:CLOUDFLARE_D1_NAME } else { $script:DEFAULT_D1_NAME }
$kvTitle = if ($env:CLOUDFLARE_KV_TITLE) { $env:CLOUDFLARE_KV_TITLE } else { $script:DEFAULT_KV_TITLE }

if ($env:SKIP_CONFIG -ne "true") {
  $workerName = Get-PromptValue "Worker name" $workerName
  $r2Bucket = Get-PromptValue "R2 bucket name" $r2Bucket
  $d1Name = Get-PromptValue "D1 database name" $d1Name
}

Write-Info "Generating Terraform…"
& $py -m cloudbooter.cli deploy `
  --account-id $accountId `
  --api-token $apiToken `
  --worker-name $workerName `
  --r2-bucket $r2Bucket `
  --d1-name $d1Name `
  --kv-title $kvTitle `
  --workers-cpu-ms $cpuMs `
  --output-dir . `
  --no-auto-deploy `
  --non-interactive

Write-Ok "Terraform files written"

if ($env:AUTO_DEPLOY -eq "true") {
  if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
    throw "terraform not found"
  }
  $env:TF_VAR_cloudflare_api_token = $apiToken
  terraform init -input=false
  terraform plan -input=false -out=tfplan
  terraform apply -input=false tfplan
  Write-Ok "Apply complete"
} else {
  Write-Info "Skipping apply (set AUTO_DEPLOY=true to apply)."
}

Write-Ok "Done."

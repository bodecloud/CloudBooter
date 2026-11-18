#Requires -Version 5.1
<#
.SYNOPSIS
  Offline wrapper regressions. Runs PowerShell code with mocked cloud tools only.
#>
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path $repoRoot ('.tmp/provider-wrappers-' + [Guid]::NewGuid().ToString('N'))
$environmentNames = @('GCP_ZONE', 'CF_MODE', 'CLOUDFLARE_WORKERS_CPU_MS', 'CLOUDFLARE_ALLOW_PAID_RESOURCES', 'CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_TOKEN', 'NON_INTERACTIVE', 'AUTO_DEPLOY', 'SKIP_CONFIG', 'TF_VAR_cloudflare_api_token', 'TF_VAR_credentials_file', 'TF_VAR_impersonate_service_account')
$savedEnvironment = @{}
foreach ($name in $environmentNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$script:assertionCount = 0

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    $script:assertionCount++
    Write-Host "PASS: $Message"
}

function Assert-Throws([scriptblock]$Action, [string]$Pattern, [string]$Message) {
    $exception = $null
    try { & $Action | Out-Null } catch { $exception = $_ }
    Assert-True ($null -ne $exception -and $exception.ToString() -match $Pattern) $Message
}

function Get-ScriptAst([string]$RelativePath) {
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $repoRoot $RelativePath), [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) { throw ($errors | Out-String) }
    return $ast
}

function Get-FunctionSource($Ast, [string]$Name) {
    $definition = $Ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $Name }, $true)
    if ($null -eq $definition) { throw "Missing function: $Name" }
    return $definition.Extent.Text
}

try {
    New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
    $gcpAst = Get-ScriptAst 'cloud/GCP/setup_gcp_terraform.ps1'
    $cfAst = Get-ScriptAst 'cloud/Cloudflare/setup_cloudflare_terraform.ps1'
    foreach ($name in @('Invoke-Gcloud', 'Assert-FreeTier', 'New-ProviderTf', 'New-VariablesTf', 'New-MainTf', 'Invoke-TerraformApplyWithRetry', 'Test-QuotaError')) {
        . ([scriptblock]::Create((Get-FunctionSource $gcpAst $name)))
    }
    function Write-Dbg { param($m) }
    function Write-OK { param($m) }
    function Write-Info { param($m) }
    function Write-Warn { param($m) }
    function Write-Err { param($m) }
    function Write-Hdr { param($m) }

    $ProjectId = 'test-project'
    $script:MockGcloudExit = 0
    $script:MockGcloudOutput = '[{"name":"existing-vm","status":"RUNNING"}]'
    function gcloud {
        $script:GcloudArguments = @($args)
        $global:LASTEXITCODE = $script:MockGcloudExit
        $script:MockGcloudOutput
    }
    $inventory = Invoke-Gcloud @('compute', 'instances', 'list')
    Assert-True (($script:GcloudArguments[0..2] -join ' ') -eq 'compute instances list' -and $inventory.name -eq 'existing-vm') 'GCP inventory preserves subcommands and parses results'
    $script:MockGcloudExit = 9
    Assert-Throws { Invoke-Gcloud @('compute', 'instances', 'list') } 'gcloud inventory failed' 'GCP inventory rejects CLI failures'
    $script:MockGcloudExit = 0
    $script:MockGcloudOutput = ''
    Assert-Throws { Invoke-Gcloud @('compute', 'instances', 'list') } 'invalid inventory JSON' 'GCP inventory rejects empty responses'
    $script:MockGcloudOutput = 'invalid JSON'
    Assert-Throws { Invoke-Gcloud @('compute', 'instances', 'list') } 'invalid inventory JSON' 'GCP inventory rejects invalid JSON'

    $env:GCP_ZONE = $null
    $Region = 'us-west1'
    $zoneParameter = $gcpAst.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq 'Zone' }
    $Zone = & ([scriptblock]::Create($zoneParameter.DefaultValue.Extent.Text))
    Assert-True ($Zone -eq 'us-west1-a') 'GCP zone default follows the selected region'
    $FREE_COMPUTE_REGIONS = @('us-central1', 'us-west1', 'us-east1')
    $FREE_STANDARD_PD_GB = 30
    $FREE_MACHINE_TYPE = 'e2-micro'
    $ExistingInstances = @{}
    $InstanceName = 'regression-vm'
    $BootDiskGb = 20
    $AllowPaidResources = $true
    $Zone = 'us-central1-a'
    Assert-Throws { Assert-FreeTier } 'zone and region do not match' 'GCP rejects mismatched zone even with paid resources allowed'
    $Zone = 'us-west1-a'

    $TfOutputDir = Join-Path $testRoot 'gcp'
    New-Item -ItemType Directory -Path $TfOutputDir -Force | Out-Null
    $TfBackend = 'local'
    $TfBackendBucket = ''
    $CredentialsFile = 'C:\credential files\service "test".json'
    $ImpersonateSa = 'target@test-project.iam.gserviceaccount.com'
    $SshPublicKey = 'ssh-ed25519 AAAATEST regression'
    $SshKeyFile = 'C:\Users\Test Person\.ssh\cloudbooter_gcp'
    $env:TF_VAR_credentials_file = 'caller-credentials.json'
    $env:TF_VAR_impersonate_service_account = 'caller@test-project.iam.gserviceaccount.com'
    New-ProviderTf
    New-VariablesTf
    New-MainTf
    $variables = Get-Content (Join-Path $TfOutputDir 'variables.tf') -Raw
    $provider = Get-Content (Join-Path $TfOutputDir 'provider.tf') -Raw
    $main = Get-Content (Join-Path $TfOutputDir 'main.tf') -Raw
    $credentialDefault = [regex]::Match($variables, '(?s)variable "credentials_file"\s*\{.*?default\s*=\s*([^\r\n]+)').Groups[1].Value | ConvertFrom-Json
    $impersonationDefault = [regex]::Match($variables, '(?s)variable "impersonate_service_account"\s*\{.*?default\s*=\s*([^\r\n]+)').Groups[1].Value | ConvertFrom-Json
    Assert-True ($credentialDefault -eq $CredentialsFile.Replace('\', '/') -and $provider.Contains('file(var.credentials_file)')) 'Generated credential default preserves quoted Windows paths'
    Assert-True ($impersonationDefault -eq $ImpersonateSa -and $provider.Contains('var.impersonate_service_account')) 'Generated impersonation variable includes selected account'
    Assert-True ($env:TF_VAR_credentials_file -eq 'caller-credentials.json' -and $env:TF_VAR_impersonate_service_account -eq 'caller@test-project.iam.gserviceaccount.com') 'GCP generation preserves caller Terraform overrides'
    $sshExpression = [regex]::Match($main, '(?m)^\s*value\s*=\s*("ssh [^\r\n]+)').Groups[1].Value
    $sshCommand = $sshExpression | ConvertFrom-Json
    Assert-True ($sshCommand.StartsWith('ssh -i "C:/Users/Test Person/.ssh/cloudbooter_gcp" ubuntu@${google_compute_instance.') -and -not $sshCommand.Contains('ubuntu:')) 'Generated SSH command has valid escaping, quoted key path, and user@host'

    $RETRY_MAX_ATTEMPTS = 2
    $RETRY_BASE_DELAY = 0
    $GCP_RETRY_PATTERNS = @('quotaExceeded')
    $script:GcpTerraformCalls = [Collections.Generic.List[string]]::new()
    function terraform {
        $operation = [string]$args[1]
        $script:GcpTerraformCalls.Add($operation)
        $global:LASTEXITCODE = 1
        if ($operation -eq 'apply') { 'quotaExceeded' } else { 'failed replacement plan' }
    }
    Assert-Throws { Invoke-TerraformApplyWithRetry } 're-plan failed' 'GCP retries stop if refreshing the saved plan fails'
    Assert-True (($script:GcpTerraformCalls -join ',') -eq 'apply,plan') 'GCP does not reapply a stale saved plan'
    # Execute Cloudflare's real top-level flow with the dependency helper replaced.
    # No Python interpreter or Terraform process is started.
    foreach ($name in @('Write-Info', 'Write-Ok', 'Write-Warn', 'Write-Err', 'Get-PromptValue')) {
        . ([scriptblock]::Create((Get-FunctionSource $cfAst $name)))
    }
    function Ensure-PythonDeps { 'Invoke-MockedCli' }
    function Resolve-CfMode { 'api' }
    function Invoke-MockedCli {
        $script:CliArguments = @($args)
        if ($script:FailCommand -eq 'generate') { $global:LASTEXITCODE = 3 } else { $global:LASTEXITCODE = 0 }
    }
    function terraform {
        $operation = [string]$args[0]
        $script:TerraformCalls.Add($operation)
        if ($script:FailCommand -eq $operation) { $global:LASTEXITCODE = 4 } else { $global:LASTEXITCODE = 0 }
    }
    $cfMainText = ($cfAst.EndBlock.Statements | Where-Object {
        $_ -isnot [System.Management.Automation.Language.FunctionDefinitionAst] -and $_.Extent.Text -notmatch '^Set-Location\b'
    } | ForEach-Object { $_.Extent.Text }) -join "`n"
    $cfMain = [scriptblock]::Create($cfMainText)
    $env:CLOUDFLARE_ACCOUNT_ID = 'offline-account'
    $env:CLOUDFLARE_API_TOKEN = 'offline-test-token'
    $env:CLOUDFLARE_WORKERS_CPU_MS = '10'
    $env:CLOUDFLARE_ALLOW_PAID_RESOURCES = 'false'
    $env:NON_INTERACTIVE = 'true'
    $env:AUTO_DEPLOY = 'true'
    $env:SKIP_CONFIG = 'true'
    $env:TF_VAR_cloudflare_api_token = 'caller-test-token'
    $script:FailCommand = ''
    $script:TerraformCalls = [Collections.Generic.List[string]]::new()
    & $cfMain | Out-Null
    Assert-True (($script:CliArguments[0..2] -join ' ') -eq '-m cloudbooter deploy') 'Cloudflare invokes the executable package entry point'
    Assert-True (($script:TerraformCalls -join ',') -eq 'init,plan,apply') 'Cloudflare successful generation proceeds through Terraform'
    Assert-True ($env:TF_VAR_cloudflare_api_token -eq 'caller-test-token') 'Cloudflare preserves caller Terraform token'
    foreach ($case in @(
        @{ Command = 'generate'; Pattern = 'generation failed'; Expected = '' },
        @{ Command = 'init'; Pattern = 'terraform init failed'; Expected = 'init' },
        @{ Command = 'plan'; Pattern = 'terraform plan failed'; Expected = 'init,plan' },
        @{ Command = 'apply'; Pattern = 'terraform apply failed'; Expected = 'init,plan,apply' }
    )) {
        $script:FailCommand = $case.Command
        $script:TerraformCalls = [Collections.Generic.List[string]]::new()
        Assert-Throws { & $cfMain } $case.Pattern "Cloudflare reports $($case.Command) failure"
        Assert-True (($script:TerraformCalls -join ',') -eq $case.Expected) "Cloudflare stops after $($case.Command) failure"
    }

    $cfShell = Get-Content (Join-Path $repoRoot 'cloud/Cloudflare/setup_cloudflare_terraform.sh') -Raw
    Assert-True ($cfShell.Contains('python3 -m cloudbooter deploy') -and -not $cfShell.Contains('-m cloudbooter.cli')) 'Cloudflare Bash wrapper selects the executable package'
    $gcpShell = Get-Content (Join-Path $repoRoot 'cloud/GCP/setup_gcp_terraform.sh') -Raw
    Assert-True ($gcpShell.Contains('zone="${GCP_ZONE:-${region}-a}"') -and $gcpShell.Contains('Zone ''${zone}'' must belong to region') -and -not $gcpShell.Contains('${DEFAULT_ZONE}')) 'GCP Bash zone default and consistency guard match PowerShell'
    Assert-True ($gcpShell.Contains('default     = $(jq -Rn --arg value "${credentials_file}" ''$value'')') -and $gcpShell.Contains('default     = $(jq -Rn --arg value "${impersonate_sa}" ''$value'')')) 'GCP Bash auth defaults are JSON escaped'

    # Exercise the CI Git pathspecs against root and deeply nested fixtures.
    $fixture = Join-Path $testRoot 'backend-fixture'
    New-Item -ItemType Directory -Path $fixture -Force | Out-Null
    & git -C $fixture init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize Git fixture.' }
    $blocked = @('backend.tf', 'backend/root.tf', 'cloud/OCI/backend.tf', 'cloud/GCP/backend/state.tf', 'cloud/GCP/backend/nested/state.tf')
    foreach ($relativePath in $blocked + @('main.tf', 'backend/readme.md', 'cloud/GCP/not-backend.tf')) {
        $fixturePath = Join-Path $fixture $relativePath
        New-Item -ItemType Directory -Path (Split-Path $fixturePath -Parent) -Force | Out-Null
        Set-Content -LiteralPath $fixturePath -Value '# fake regression fixture; contains no credentials'
    }
    & git -C $fixture -c core.autocrlf=false add -f -- .
    if ($LASTEXITCODE -ne 0) { throw 'Could not populate Git fixture.' }
    $patterns = @(':(glob)**/backend.tf', ':(glob)**/backend/**/*.tf')
    $workflow = Get-Content (Join-Path $repoRoot '.github/workflows/ci.yml') -Raw
    foreach ($pattern in $patterns) { Assert-True ($workflow.Contains("'$pattern'")) "CI uses recursive backend pathspec $pattern" }
    $found = @(& git -C $fixture ls-files -- @patterns)
    Assert-True ((($found | Sort-Object) -join ',') -eq (($blocked | Sort-Object) -join ',')) 'CI backend pathspecs block nested Terraform state configuration without matching unrelated files'
    Write-Host "All $script:assertionCount wrapper regressions passed."
} finally {
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    $resolvedRoot = [IO.Path]::GetFullPath($repoRoot).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
    if (-not $resolvedTestRoot.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing cleanup outside repository.' }
    if (Test-Path -LiteralPath $resolvedTestRoot) { Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force }
}

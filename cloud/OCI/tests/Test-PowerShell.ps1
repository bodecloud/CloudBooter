# Standalone regression checks: no cloud tools, credentials, or Python required.
$ErrorActionPreference = 'Stop'
$providerRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $providerRoot 'setup_oci_terraform.ps1'
$tokens = $null
$parseErrors = $null
$sourceAst = [System.Management.Automation.Language.Parser]::ParseFile($sourcePath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw ($parseErrors.Message -join "`n") }
$names = @(
    'safe_jq', 'tokenize_cmd_string', 'inventory_compute_instances',
    'inventory_networking_resources', 'inventory_storage_resources',
    'Wait-ForInstanceState', 'Resize-LegacyArmInstances', 'out_of_capacity_auto_apply',
    'load_existing_config', 'create_terraform_variables', 'create_terraform_block_volumes', 'create_terraform_main',
    'convert_to_hcl_string', 'get_terraform_auth_config', 'read_oci_config_value', 'create_terraform_provider'
)
$functions = $sourceAst.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in $names
}, $true)
foreach ($definition in $functions) { . ([scriptblock]::Create($definition.Extent.Text)) }
function print_status { param($message) }
function print_header { param($message) }
function print_success { param($message) }
function print_warning { param($message) }
function print_error { param($message) }
function print_debug { param($message) }
function calculate_available_resources { }
function configure_terraform_backend { }
function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -cne $Expected) { throw "$Message (expected '$Expected', got '$Actual')" }
}
function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

# Single-element arrays occur in the normal one-VNIC response.
Assert-Equal (safe_jq '[{"vnic-id":"vnic-1"}]' '.[0]."vnic-id"' 'missing') 'vnic-1' 'Single-element JSON array lost'
Assert-Equal (safe_jq '[{"vnic-id":"vnic-1"},{"vnic-id":"vnic-2"}]' '.[1]."vnic-id"' 'missing') 'vnic-2' 'Multiple-element JSON array changed'
Assert-Equal (safe_jq '[]' '.[0]."vnic-id"' 'missing') 'missing' 'Empty-array fallback changed'
Assert-Equal (safe_jq '{"data":{"shape-config":{"ocpus":2}}}' '.data."shape-config".ocpus') '2' 'Object properties changed'

# Capture tokenized CLI arguments without launching OCI.
$script:queries = @()
function oci_cmd {
    $arguments = @(tokenize_cmd_string ($args -join ' '))
    $queryIndex = [array]::IndexOf($arguments, '--query')
    if ($queryIndex -ge 0) { $script:queries += $arguments[$queryIndex + 1] }
    switch -Wildcard ($args -join ' ') {
        'compute instance list *' { return '[{"id":"instance-1","name":"arm-one","state":"RUNNING","shape":"VM.Standard.A1.Flex"}]' }
        'compute vnic-attachment list *' { return '[{"vnic-id":"vnic-1"}]' }
        'network vnic get *' { return '{"data":{"public-ip":"203.0.113.1","private-ip":"10.0.0.2"}}' }
        'compute instance get *--raw-output*' { return 'RUNNING' }
        'compute instance get *' { return '{"data":{"shape-config":{"ocpus":2,"memory-in-gbs":12}}}' }
        'network vcn list *' { return '[{"id":"vcn-1","name":"network","cidr":"10.0.0.0/16"}]' }
        default { return '[]' }
    }
}
$script:tenancy_ocid = 'tenancy-test'
$script:availability_domain = 'AD-1'
$script:EXISTING_NON_FREE_SHAPE_NAMES = @()
$FREE_TIER_AMD_SHAPE = 'VM.Standard.E2.1.Micro'
$FREE_TIER_ARM_SHAPE = 'VM.Standard.A1.Flex'
$FREE_TIER_MAX_AMD_INSTANCES = 2
$FREE_TIER_MAX_ARM_INSTANCES = 2
$FREE_TIER_MAX_ARM_OCPUS = 2
$FREE_TIER_MAX_ARM_MEMORY_GB = 12
$FREE_TIER_MAX_STORAGE_GB = 200
$FREE_TIER_MAX_VCNS = 2
$FREE_TIER_DEFAULT_ARM_OCPUS = 2
$FREE_TIER_DEFAULT_ARM_MEMORY_GB = 12
inventory_compute_instances
Assert-Equal $script:EXISTING_ARM_INSTANCES.Count 1 'Existing ARM instance was lost'
Assert-True ($script:EXISTING_ARM_INSTANCES['instance-1'].Contains('|203.0.113.1|10.0.0.2|')) 'Single VNIC IP discovery failed'
inventory_networking_resources
inventory_storage_resources
Assert-True (Wait-ForInstanceState -InstanceId 'instance-1' -TimeoutSec 1) 'Instance state query did not return RUNNING'
$expectedQueries = @(
    'data[?"lifecycle-state"!=`"TERMINATED"`].{id:id,name:"display-name",state:"lifecycle-state",shape:shape,ad:"availability-domain",created:"time-created"}',
    'data[?"lifecycle-state"==`"ATTACHED"`]',
    'data[?"lifecycle-state"==`"AVAILABLE"`].{id:id,name:"display-name",cidr:"cidr-block"}',
    'data[?"lifecycle-state"==`"AVAILABLE"`].{id:id,name:"display-name"}',
    'data[].{id:id,name:"display-name"}',
    'data[?"lifecycle-state"==`"AVAILABLE"`].{id:id,name:"display-name",size:"size-in-gbs"}',
    'data."lifecycle-state"'
)
foreach ($query in $expectedQueries) { Assert-True ($script:queries -ccontains $query) "Malformed or missing OCI query: $query" }

# Successful resizes update inventory without invalidating its enumerator.
function Get-LegacyArmInstanceCount { return 2 }
$script:resizeCalls = 0
function Resize-ArmInstanceToBillingSafe { $script:resizeCalls++; return $true }
$script:EXISTING_ARM_INSTANCES = @{
    first = 'first|RUNNING|VM.Standard.A1.Flex|none|none|4|24'
    second = 'second|RUNNING|VM.Standard.A1.Flex|none|none|4|24'
}
Assert-Equal (Resize-LegacyArmInstances) 0 'Legacy resize reported failure'
Assert-Equal $script:resizeCalls 2 'Legacy resize stopped after the first instance'
foreach ($entry in $script:EXISTING_ARM_INSTANCES.Values) { Assert-True ($entry.EndsWith('|2|12')) 'Resized inventory was not updated' }

# A failed saved-plan apply may already have changed state and must stop.
$script:applyCalls = 0
function terraform { $script:applyCalls++; $global:LASTEXITCODE = 1; 'Error: Out of host capacity' }
Assert-Equal (out_of_capacity_auto_apply) $false 'Failed apply was reported as success'
Assert-Equal $script:applyCalls 1 'A potentially stale saved plan was retried'
function terraform { $script:applyCalls++; $global:LASTEXITCODE = 0 }
Assert-Equal (out_of_capacity_auto_apply) $true 'Successful apply was not reported'

$temporaryRoot = Join-Path $providerRoot ('.test-powershell-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
Push-Location $temporaryRoot
try {
    # Saved disk sizes must survive load -> regenerate, including sparse disks.
    @"
locals {
  amd_micro_instance_count = 0
  arm_flex_instance_count = 2
  arm_flex_ocpus_per_instance = [1, 1]
  arm_flex_memory_per_instance = [6, 6]
  arm_flex_boot_volume_size_gb = [50, 50]
  arm_flex_hostnames = ["first", "second"]
  arm_block_volume_sizes = [0, 50]
}
"@ | Set-Content 'variables.tf'
    Assert-True (load_existing_config) 'Saved configuration did not load'
    Assert-Equal ($script:arm_flex_block_volumes -join ',') '0,50' 'Saved block-volume sizes were lost'
    $script:user_ocid = 'user-test'
    $script:region = 'region-test'
    $script:ubuntu_image_ocid = 'image-x86-test'
    $script:ubuntu_arm_flex_image_ocid = 'image-arm-test'
    $script:ssh_key_basename = 'id_test'
    create_terraform_variables
    Assert-True ((Get-Content 'variables.tf' -Raw) -match 'arm_block_volume_sizes\s*=\s*\[0, 50\]') 'Regeneration changed optional disks'
    create_terraform_block_volumes
    $blockHcl = Get-Content 'block_volumes.tf' -Raw
    Assert-True ($blockHcl.Contains('arm_block_volume_indices = [for index, size in local.arm_block_volume_sizes : index if size > 0]')) 'Disk original indices were lost'
    Assert-True ($blockHcl.Contains('oci_core_instance.arm[local.arm_block_volume_indices[count.index]].id')) 'Disk attachment does not use original instance index'
    Assert-True ($blockHcl.Contains('local.arm_flex_hostnames[local.arm_block_volume_indices[count.index]]')) 'Disk names do not use original instance index'
    # Boot performance must use Balanced, with all canonical layers in sync.
    $powershellSource = Get-Content $sourcePath -Raw
    Assert-True ($powershellSource -match '\$FREE_TIER_BOOT_VOLUME_VPU\s*=\s*(\d+)') 'PowerShell boot performance constant missing'
    $FREE_TIER_BOOT_VOLUME_VPU = [int]$matches[1]
    Assert-Equal $FREE_TIER_BOOT_VOLUME_VPU 10 'Boot volume performance must use the Balanced default'
    create_terraform_main
    $mainHcl = Get-Content 'main.tf' -Raw
    Assert-True ($mainHcl -match 'boot_volume_vpus_per_gb\s*=\s*10\b') 'Generated boot volume selects paid Ultra High Performance'
    Assert-True ($mainHcl -match 'protocol\s*=\s*"58"\s+source\s*=\s*"::/0"') 'IPv6 ICMP ingress must use ICMPv6 protocol 58'
    Assert-True (-not ($mainHcl -match 'protocol\s*=\s*"1"\s+source\s*=\s*"::/0"')) 'IPv4 ICMP protocol was used with an IPv6 source'
    Assert-True (-not ($mainHcl -match 'boot_volume_vpus_per_gb\s*=\s*120\b')) 'Legacy Ultra High Performance leaked into Terraform'
    $pythonConstants = Get-Content (Join-Path $providerRoot 'src/cloudbooter/free_tier.py') -Raw
    Assert-True ($pythonConstants -match 'boot_volume_vpu:\s*int\s*=\s*10\b') 'Canonical OCI performance constant differs from PowerShell'
    $pythonTests = Get-Content (Join-Path $providerRoot 'tests/test_free_tier.py') -Raw
    Assert-True ($pythonTests.Contains('assert LIMITS.boot_volume_vpu == 10')) 'Canonical OCI test expects different boot performance'
    foreach ($relativeDoc in @('README.md', 'docs/FREE_TIER_LIMITS.md', 'docs/QUICKSTART.md')) {
        $docText = Get-Content (Join-Path $providerRoot $relativeDoc) -Raw
        Assert-True ($docText.Contains('10 VPU (Balanced)')) "Boot performance documentation differs: $relativeDoc"
        Assert-True (-not $docText.Contains('120 VPU')) "Outdated boot performance documentation: $relativeDoc"
    }
    # Non-default profiles and API-key custom configs must reach Terraform.
    $_ociHome = Join-Path $temporaryRoot 'user-home'
    $OCI_PROFILE = 'TEAM'
    $OCI_CONFIG_FILE = Join-Path (Join-Path $_ociHome '.oci') 'config'
    $script:auth_method = 'security_token'
    $originalCliAuth = $env:OCI_CLI_AUTH
    try {
        $env:OCI_CLI_AUTH = $null
        create_terraform_provider
        $providerHcl = Get-Content 'provider.tf' -Raw
        Assert-True ($providerHcl.Contains('required_version = ">= 1.5"')) 'Generated check blocks require Terraform 1.5 or later'
        Assert-True ($providerHcl.Contains('auth = "SecurityToken"')) 'Session auth changed unexpectedly'
        Assert-True ($providerHcl.Contains('config_file_profile = "TEAM"')) 'Selected OCI profile was ignored'
        $script:auth_method = 'api_key'
        create_terraform_provider
        Assert-True ((Get-Content 'provider.tf' -Raw).Contains('auth = "APIKey"')) 'API-key auth was replaced with session auth'
        $OCI_CONFIG_FILE = Join-Path $temporaryRoot 'custom-config'
        @"
[TEAM]
tenancy=tenancy-test
user=user-test
fingerprint=fingerprint-test
key_file=./fake-api-key.pem
"@ | Set-Content $OCI_CONFIG_FILE
        create_terraform_provider
        $providerHcl = Get-Content 'provider.tf' -Raw
        Assert-True ($providerHcl.Contains('private_key_path = pathexpand("./fake-api-key.pem")')) 'Custom config key path was ignored'
        Assert-True ($providerHcl.Contains('tenancy_ocid = "tenancy-test"')) 'Custom config tenancy was ignored'
        Assert-True (-not $providerHcl.Contains('config_file_profile')) 'Custom config incorrectly falls back to the home profile'
        $script:auth_method = 'security_token'
        $rejectedCustomToken = $false
        try { get_terraform_auth_config | Out-Null }
        catch { $rejectedCustomToken = $_.Exception.Message.Contains('reads ~/.oci/config') }
        Assert-True $rejectedCustomToken 'Unsupported custom session config silently fell back to another account'
        $env:OCI_CLI_AUTH = 'instance_principal'
        Assert-True ((get_terraform_auth_config).Contains('auth = "InstancePrincipal"')) 'OCI_CLI_AUTH override was ignored'
    }
    finally { $env:OCI_CLI_AUTH = $originalCliAuth }
    $bashSource = Get-Content (Join-Path $providerRoot 'setup_oci_terraform.sh') -Raw
    Assert-True ($bashSource.Contains('oci_core_instance.arm[local.arm_block_volume_indices[count.index]].id')) 'Bash generator has a different disk attachment mapping'
    Assert-True ($bashSource.Contains('FREE_TIER_BOOT_VOLUME_VPU=10')) 'Bash boot performance differs from canonical Balanced default'
    Assert-True ($bashSource.Contains('required_version = ">= 1.5"')) 'Bash check blocks require Terraform 1.5 or later'
    foreach ($mapping in @('apikey) provider_auth="APIKey"', 'securitytoken) provider_auth="SecurityToken"', 'instanceprincipal) provider_auth="InstancePrincipal"', 'resourceprincipal) provider_auth="ResourcePrincipal"')) {
        Assert-True ($bashSource.Contains($mapping)) "Bash provider auth mapping missing: $mapping"
    }
    Assert-True ($bashSource.Contains('local selected_auth="${OCI_CLI_AUTH:-$auth_method}"')) 'Bash Terraform auth ignores the caller override'
    Assert-True ($bashSource.Contains('config_file_profile = $(terraform_hcl_string "$OCI_PROFILE")')) 'Bash Terraform profile is hardcoded'
    Assert-True ($bashSource.Contains('the Bash generator does not support a custom OCI_CONFIG_FILE.')) 'Custom Bash config path must fail clearly'
    Assert-True ($bashSource.Contains('create_terraform_provider || return $?')) 'Bash generation ignores a provider authentication failure'
    Assert-True ($bashSource.Contains('jq -Rs')) 'Bash provider values must use JSON escaping'
    Assert-True (-not ($bashSource -match 'protocol\s*=\s*"1"\s+source\s*=\s*"::/0"')) 'Bash must not use IPv4 ICMP protocol with an IPv6 source'
}
finally {
    Pop-Location
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedProviderRoot = [System.IO.Path]::GetFullPath($providerRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedTemporaryRoot.StartsWith($resolvedProviderRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Test cleanup path escaped the provider directory' }
    Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
}
Write-Host 'All OCI PowerShell regression checks passed.'
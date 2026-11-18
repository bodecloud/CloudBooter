[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$checks = 0
function Assert-Static([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:checks++
}
function Read-Source([string]$Path) { Get-Content -LiteralPath (Join-Path $repo $Path) -Raw }
$goRoot = Join-Path $repo 'implementations/go/cmd/setup-oci-terraform'
$declarations = @{}
foreach ($file in Get-ChildItem -LiteralPath $goRoot -Filter '*.go') {
    $source = Get-Content -LiteralPath $file.FullName -Raw
    foreach ($match in [regex]::Matches($source, '(?m)^func (?:\([^)]*\) )?(?<name>\w+)\(')) {
        $name = $match.Groups['name'].Value
        Assert-Static (-not $declarations.ContainsKey($name)) "Duplicate Go declaration: $name"
        $declarations[$name] = $file.Name
    }
    $imports = [regex]::Match($source, '(?s)import \((?<body>.*?)\)')
    $body = $source.Remove($imports.Index, $imports.Length)
    foreach ($match in [regex]::Matches($imports.Groups['body'].Value, '"(?<path>[^"]+)"')) {
        $package = ($match.Groups['path'].Value -split '/')[-1]
        Assert-Static ([regex]::IsMatch($body, '\b'+[regex]::Escape($package)+'\.')) "Unused Go import in $($file.Name): $package"
    }
}
$main = Read-Source 'implementations/go/cmd/setup-oci-terraform/main.go'
$config = Read-Source 'implementations/go/cmd/setup-oci-terraform/config.go'
$renderer = Read-Source 'implementations/go/cmd/setup-oci-terraform/filegen.go'
$python = Read-Source 'implementations/python/setup_oci_terraform.py'
Assert-Static ($main -match 'FreeTierMaxARMOCPUs\s*=\s*2\b' -and $main -match 'FreeTierMaxARMMemoryGB\s*=\s*12\b') 'Go legacy caps must match 2 OCPU / 12 GB baseline'
Assert-Static ($python -match 'FREE_TIER_MAX_ARM_OCPUS = 2\b' -and $python -match 'FREE_TIER_MAX_ARM_MEMORY_GB = 12\b') 'Python legacy caps must match 2 OCPU / 12 GB baseline'
Assert-Static (-not $renderer.Contains('\${')) 'Raw Go Terraform contains invalid backslash-dollar escapes'
Assert-Static ($renderer.Contains('required_version = ">= 1.5"')) 'Terraform check blocks require Terraform 1.5 or newer'
Assert-Static ($python.Contains('required_version = ">= 1.5"') -and -not $python.Contains('required_version = ">= 1.0"')) 'Python Terraform check blocks require Terraform 1.5 or newer'
foreach ($resource in @('oci_core_vcn','oci_core_internet_gateway','oci_core_default_route_table','oci_core_default_security_list','oci_core_subnet')) {
    Assert-Static ($renderer.Contains('resource "'+$resource+'" "main"')) "Go renderer missing $resource.main"
}
foreach ($name in @('amd','arm')) { Assert-Static ($renderer.Contains('resource "oci_core_instance" "'+$name+'"')) "Go renderer missing $name instances" }
# Validate the static resource/data reference graph in generated Go templates.
$declared = @{}
foreach ($match in [regex]::Matches($renderer, '(?<kind>resource|data) "(?<type>oci_\w+)" "(?<name>\w+)"')) {
    $prefix = if ($match.Groups['kind'].Value -eq 'data') { 'data.' } else { '' }
    $declared[$prefix+$match.Groups['type'].Value+'.'+$match.Groups['name'].Value] = $true
}
foreach ($match in [regex]::Matches($renderer, '\b(?<reference>(?:data\.)?oci_\w+\.\w+)')) {
    Assert-Static ($declared.ContainsKey($match.Groups['reference'].Value)) "Undeclared Terraform reference: $($match.Value)"
}
foreach ($field in @('amd_micro_hostnames','arm_flex_hostnames','arm_flex_ocpus_per_instance','arm_flex_memory_per_instance','arm_flex_boot_volume_size_gb','arm_block_volume_sizes')) {
    Assert-Static ($config.Contains('"'+$field+'":')) "Go saved configuration omits $field"
}
Assert-Static ($config.Contains('remainingOCPUs-remainingInstances') -and $config.Contains('remainingStorage-remainingInstances*FreeTierMinBootVolumeGB')) 'Go allocation must reserve capacity for remaining instances'
Assert-Static ($config.Contains('remainingStorage >= FreeTierMinBootVolumeGB')) 'Go maximum configuration must respect remaining storage'
Assert-Static ($renderer.Contains('configFile != defaultConfigFile')) 'Go must reject unsupported custom OCI config paths before generation'
Assert-Static ($renderer.Contains('validateInstanceConfig(app.InstanceConfig)')) 'Go must validate caps before writing Terraform'
foreach ($source in @($renderer,$python)) {
    Assert-Static ($source.Contains('tostring(index) => size if size > 0') -and $source.Contains('oci_core_instance.arm[tonumber(each.key)].id')) 'ARM volumes must preserve original instance indices'
}
foreach ($path in @('implementations/python/setup.py','implementations/python/pyproject.toml')) {
    $metadata = Read-Source $path
    Assert-Static ($metadata.Contains('setup_oci_terraform:main') -and -not $metadata.Contains('oci_terraform_setup.cli')) "Broken entry point in $path"
    Assert-Static (-not $metadata.Contains('where="src"') -and -not $metadata.Contains('where = ["src"]')) "Nonexistent package directory in $path"
}
Assert-Static ($python.IndexOf('args = parser.parse_args()') -lt $python.IndexOf('    # Phase 1: Prerequisites')) 'Python CLI flags must be parsed before provisioning'
Assert-Static ($python.Contains('if attempt > 1:') -and $python.Contains('replanned.returncode')) 'Python retries must refresh partially applied plans'
$oci = Read-Source 'implementations/go/cmd/setup-oci-terraform/oci_client.go'
Assert-Static ($oci.Contains('common.ConfigurationProviderForSessionTokenWithProfile') -and $oci.Contains('app.Config.OCIProfile, "")')) 'Go must select a session-token provider and pass the SDK string password argument'
$inventory = Read-Source 'implementations/go/cmd/setup-oci-terraform/inventory.go'
Assert-Static ($inventory.Contains('app.ComputeClient.ListVnicAttachments')) 'OCI VNIC attachments must use ComputeClient'
$retry = Read-Source 'helper_scripts/out_of_capacity.sh'
Assert-Static ($retry.Contains('mkdir -p -- "$(dirname -- "$LOGFILE")"')) 'Retry helper must create the log directory'
Assert-Static ($retry.Contains('terraform plan -input=false -out="$PLAN_FILE"')) 'Retry helper must refresh a partially applied saved plan'
Write-Output "Passed $checks static legacy implementation checks. Go/Python/Bash runtimes and cloud deployments were not executed."

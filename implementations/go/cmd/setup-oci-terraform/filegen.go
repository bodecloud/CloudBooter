package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"strconv"
	"time"
)

// Create all Terraform files
func (app *App) createTerraformFiles() error {
	// The OCI Terraform provider reads the standard config path. Reject a
	// different CLI config before writing files for a potentially different account.
	homeDir, err := os.UserHomeDir()
	if err != nil { return err }
	configFile, err := filepath.Abs(app.Config.OCIConfigFile)
	if err != nil { return err }
	defaultConfigFile, err := filepath.Abs(filepath.Join(homeDir, ".oci", "config"))
	if err != nil { return err }
	if configFile != defaultConfigFile { return fmt.Errorf("Terraform generation requires the standard OCI config path %s; custom --oci-config paths are unsupported", defaultConfigFile) }
	if err := validateInstanceConfig(app.InstanceConfig); err != nil { return err }
	if app.InstanceConfig.AMDMicroInstanceCount > 0 && app.OCIConfig.UbuntuImageOCID == "" { return fmt.Errorf("no AMD image available") }
	if app.InstanceConfig.ARMFlexInstanceCount > 0 && app.OCIConfig.UbuntuARMFlexImageOCID == "" { return fmt.Errorf("no ARM image available") }
	printHeader("GENERATING TERRAFORM FILES")

	if err := app.createTerraformProvider(); err != nil {
		return err
	}

	if err := app.createTerraformVariables(); err != nil {
		return err
	}

	if err := app.createTerraformDatasources(); err != nil {
		return err
	}

	if err := app.createTerraformMain(); err != nil {
		return err
	}

	if err := app.createTerraformBlockVolumes(); err != nil {
		return err
	}

	if err := app.createCloudInit(); err != nil {
		return err
	}

	printSuccess("All Terraform files generated successfully")
	return nil
}

// Create provider.tf
func (app *App) createTerraformProvider() error {
	printStatus("Creating provider.tf...")

	// Backup existing file
	if _, err := os.Stat("provider.tf"); err == nil {
		backupName := fmt.Sprintf("provider.tf.bak.%s", time.Now().Format("20060102_150405"))
		os.Rename("provider.tf", backupName)
	}

	content := fmt.Sprintf(`# Terraform Provider Configuration for Oracle Cloud Infrastructure
# Generated: %s
# Region: %s

terraform {
  required_version = ">= 1.5"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}

# OCI Provider with session token authentication
provider "oci" {
  auth                = %q
  config_file_profile = %q
  region              = "%s"
}
`, time.Now().Format(time.RFC3339), app.OCIConfig.Region, app.OCIConfig.AuthMethod, app.Config.OCIProfile, app.OCIConfig.Region)

	return os.WriteFile("provider.tf", []byte(content), 0644)
}

// Create variables.tf
func (app *App) createTerraformVariables() error {
	printStatus("Creating variables.tf...")

	// Backup existing file
	if _, err := os.Stat("variables.tf"); err == nil {
		backupName := fmt.Sprintf("variables.tf.bak.%s", time.Now().Format("20060102_150405"))
		os.Rename("variables.tf", backupName)
	}

	// Build array strings
	amdHostnames := buildArrayString(app.InstanceConfig.AMDMicroHostnames, true)
	armHostnames := buildArrayString(app.InstanceConfig.ARMFlexHostnames, true)
	armOCPUs := buildArrayInt(app.InstanceConfig.ARMFlexOCPUsPerInstance)
	armMemory := buildArrayInt(app.InstanceConfig.ARMFlexMemoryPerInstance)
	armBoot := buildArrayInt(app.InstanceConfig.ARMFlexBootVolumeSizeGB)
	armBlock := buildArrayInt(app.InstanceConfig.ARMFlexBlockVolumes)

	content := fmt.Sprintf(`# Oracle Cloud Infrastructure Terraform Variables
# Generated: %s
# Configuration: %dx AMD + %dx ARM instances

locals {
  # Core identifiers
  tenancy_ocid    = "%s"
  compartment_id  = "%s"
  user_ocid       = "%s"
  region          = "%s"

  # Ubuntu Images (region-specific)
  ubuntu_x86_image_ocid = "%s"
  ubuntu_arm_image_ocid = "%s"

  # SSH Configuration
  ssh_pubkey_path      = pathexpand("./ssh_keys/id_rsa.pub")
  ssh_pubkey_data      = file(pathexpand("./ssh_keys/id_rsa.pub"))
  ssh_private_key_path = pathexpand("./ssh_keys/id_rsa")

  # AMD x86 Micro Instances Configuration
  amd_micro_instance_count      = %d
  amd_micro_boot_volume_size_gb = %d
  amd_micro_hostnames           = %s
  amd_block_volume_size_gb      = 0

  # ARM A1 Flex Instances Configuration
  arm_flex_instance_count       = %d
  arm_flex_ocpus_per_instance   = %s
  arm_flex_memory_per_instance  = %s
  arm_flex_boot_volume_size_gb  = %s
  arm_flex_hostnames            = %s
  arm_block_volume_sizes        = %s

  # Storage calculations
  total_amd_storage = local.amd_micro_instance_count * local.amd_micro_boot_volume_size_gb
  total_arm_storage = local.arm_flex_instance_count > 0 ? sum(local.arm_flex_boot_volume_size_gb) : 0
  total_block_storage = (local.amd_micro_instance_count * local.amd_block_volume_size_gb) + (local.arm_flex_instance_count > 0 ? sum(local.arm_block_volume_sizes) : 0)
  total_storage = local.total_amd_storage + local.total_arm_storage + local.total_block_storage
}

# Free Tier Limits
variable "free_tier_max_storage_gb" {
  description = "Maximum storage for Oracle Free Tier"
  type        = number
  default     = %d
}

variable "free_tier_max_arm_ocpus" {
  description = "Maximum ARM OCPUs for Oracle Free Tier"
  type        = number
  default     = %d
}

variable "free_tier_max_arm_memory_gb" {
  description = "Maximum ARM memory for Oracle Free Tier"
  type        = number
  default     = %d
}

# Validation checks
check "storage_limit" {
  assert {
    condition     = local.total_storage <= var.free_tier_max_storage_gb
    error_message = "Total storage (${local.total_storage}GB) exceeds Free Tier limit (${var.free_tier_max_storage_gb}GB)"
  }
}

check "arm_ocpu_limit" {
  assert {
    condition     = local.arm_flex_instance_count == 0 || sum(local.arm_flex_ocpus_per_instance) <= var.free_tier_max_arm_ocpus
    error_message = "Total ARM OCPUs exceed Free Tier limit (${var.free_tier_max_arm_ocpus})"
  }
}

check "arm_memory_limit" {
  assert {
    condition     = local.arm_flex_instance_count == 0 || sum(local.arm_flex_memory_per_instance) <= var.free_tier_max_arm_memory_gb
    error_message = "Total ARM memory exceeds Free Tier limit (${var.free_tier_max_arm_memory_gb}GB)"
  }
}
`,
		time.Now().Format(time.RFC3339),
		app.InstanceConfig.AMDMicroInstanceCount,
		app.InstanceConfig.ARMFlexInstanceCount,
		app.OCIConfig.TenancyOCID,
		app.OCIConfig.TenancyOCID,
		app.OCIConfig.UserOCID,
		app.OCIConfig.Region,
		app.OCIConfig.UbuntuImageOCID,
		app.OCIConfig.UbuntuARMFlexImageOCID,
		app.InstanceConfig.AMDMicroInstanceCount,
		app.InstanceConfig.AMDMicroBootVolumeSizeGB,
		amdHostnames,
		app.InstanceConfig.ARMFlexInstanceCount,
		armOCPUs,
		armMemory,
		armBoot,
		armHostnames,
		armBlock,
		FreeTierMaxStorageGB,
		FreeTierMaxARMOCPUs,
		FreeTierMaxARMMemoryGB,
	)

	return os.WriteFile("variables.tf", []byte(content), 0644)
}

// Create data_sources.tf
func (app *App) createTerraformDatasources() error {
	printStatus("Creating data_sources.tf...")

	if _, err := os.Stat("data_sources.tf"); err == nil {
		backupName := fmt.Sprintf("data_sources.tf.bak.%s", time.Now().Format("20060102_150405"))
		os.Rename("data_sources.tf", backupName)
	}

	content := `# OCI Data Sources
# Fetches dynamic information from Oracle Cloud

# Availability Domains
data "oci_identity_availability_domains" "ads" {
  compartment_id = local.tenancy_ocid
}

# Tenancy Information
data "oci_identity_tenancy" "tenancy" {
  tenancy_id = local.tenancy_ocid
}

# Available Regions
data "oci_identity_regions" "regions" {}

# Region Subscriptions
data "oci_identity_region_subscriptions" "subscriptions" {
  tenancy_id = local.tenancy_ocid
}
`

	return os.WriteFile("data_sources.tf", []byte(content), 0644)
}

// Create the complete IPv4 network and AMD/ARM instance configuration.
func (app *App) createTerraformMain() error {
	printStatus("Creating main.tf...")
	if _, err := os.Stat("main.tf"); err == nil {
		backupName := fmt.Sprintf("main.tf.bak.%s", time.Now().Format("20060102_150405"))
		if err := os.Rename("main.tf", backupName); err != nil { return err }
	}
	content := `# Oracle Cloud Infrastructure - Main Configuration
# Always Free Tier Optimized

# ============================================================================
# NETWORKING
# ============================================================================

resource "oci_core_vcn" "main" {
  compartment_id = local.compartment_id
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "main-vcn"
  dns_label      = "mainvcn"

  freeform_tags = {
    "Purpose" = "AlwaysFreeTier"
    "Managed" = "Terraform"
  }
}

resource "oci_core_internet_gateway" "main" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "main-igw"
  enabled        = true
}

resource "oci_core_default_route_table" "main" {
  manage_default_resource_id = oci_core_vcn.main.default_route_table_id
  display_name               = "main-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }


}

resource "oci_core_default_security_list" "main" {
  manage_default_resource_id = oci_core_vcn.main.default_security_list_id
  display_name               = "main-sl"

  # Allow all egress
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }



  # SSH (IPv4 & IPv6)
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 22
      max = 22
    }
  }


  # HTTP (IPv4 & IPv6)
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 80
      max = 80
    }
  }


  # HTTPS (IPv4 & IPv6)
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
  }


  # ICMP (IPv4 & IPv6)
  ingress_security_rules {
    protocol = "1"
    source   = "0.0.0.0/0"
  }

}

resource "oci_core_subnet" "main" {
  compartment_id = local.compartment_id
  vcn_id         = oci_core_vcn.main.id
  cidr_block     = "10.0.1.0/24"
  display_name   = "main-subnet"
  dns_label      = "mainsubnet"

  route_table_id    = oci_core_default_route_table.main.id
  security_list_ids = [oci_core_default_security_list.main.id]
}

# ============================================================================
# COMPUTE INSTANCES
# ============================================================================

resource "oci_core_instance" "amd" {
  count = local.amd_micro_instance_count

  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = local.compartment_id
  display_name        = local.amd_micro_hostnames[count.index]
  shape               = "VM.Standard.E2.1.Micro"

  create_vnic_details {
    subnet_id        = oci_core_subnet.main.id
    display_name     = "${local.amd_micro_hostnames[count.index]}-vnic"
    assign_public_ip = true
    hostname_label   = local.amd_micro_hostnames[count.index]
  }

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_x86_image_ocid
    boot_volume_size_in_gbs = local.amd_micro_boot_volume_size_gb
  }

  metadata = {
    ssh_authorized_keys = local.ssh_pubkey_data
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      hostname = local.amd_micro_hostnames[count.index]
    }))
  }

  freeform_tags = {
    "Purpose"      = "AlwaysFreeTier"
    "InstanceType" = "AMD-Micro"
    "Managed"      = "Terraform"
  }

  lifecycle {
    ignore_changes = [source_details[0].source_id, defined_tags]
  }
}

resource "oci_core_instance" "arm" {
  count = local.arm_flex_instance_count

  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = local.compartment_id
  display_name        = local.arm_flex_hostnames[count.index]
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = local.arm_flex_ocpus_per_instance[count.index]
    memory_in_gbs = local.arm_flex_memory_per_instance[count.index]
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.main.id
    display_name     = "${local.arm_flex_hostnames[count.index]}-vnic"
    assign_public_ip = true
    hostname_label   = local.arm_flex_hostnames[count.index]
  }

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_arm_image_ocid
    boot_volume_size_in_gbs = local.arm_flex_boot_volume_size_gb[count.index]
  }

  metadata = {
    ssh_authorized_keys = local.ssh_pubkey_data
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      hostname = local.arm_flex_hostnames[count.index]
    }))
  }

  freeform_tags = {
    "Purpose"      = "AlwaysFreeTier"
    "InstanceType" = "ARM-A1-Flex"
    "Managed"      = "Terraform"
  }

  lifecycle {
    ignore_changes = [source_details[0].source_id, defined_tags]
  }
}

output "amd_instances" {
  description = "AMD instance information"
  value = local.amd_micro_instance_count > 0 ? {
    for i in range(local.amd_micro_instance_count) : local.amd_micro_hostnames[i] => {
      id         = oci_core_instance.amd[i].id
      public_ip  = oci_core_instance.amd[i].public_ip
      private_ip = oci_core_instance.amd[i].private_ip
      state      = oci_core_instance.amd[i].state
      ssh        = "ssh -i ./ssh_keys/id_rsa ubuntu@${oci_core_instance.amd[i].public_ip}"
    }
  } : {}
}

output "arm_instances" {
  description = "ARM instance information"
  value = local.arm_flex_instance_count > 0 ? {
    for i in range(local.arm_flex_instance_count) : local.arm_flex_hostnames[i] => {
      id         = oci_core_instance.arm[i].id
      public_ip  = oci_core_instance.arm[i].public_ip
      private_ip = oci_core_instance.arm[i].private_ip
      state      = oci_core_instance.arm[i].state
      ocpus      = local.arm_flex_ocpus_per_instance[i]
      memory_gb  = local.arm_flex_memory_per_instance[i]
      ssh        = "ssh -i ./ssh_keys/id_rsa ubuntu@${oci_core_instance.arm[i].public_ip}"
    }
  } : {}
}

output "network" {
  description = "Network information"
  value = {
    vcn_id     = oci_core_vcn.main.id
    vcn_cidr   = oci_core_vcn.main.cidr_blocks[0]
    subnet_id  = oci_core_subnet.main.id
    subnet_cidr = oci_core_subnet.main.cidr_block
  }
}

output "summary" {
  description = "Infrastructure summary"
  value = {
    region          = local.region
    total_amd       = local.amd_micro_instance_count
    total_arm       = local.arm_flex_instance_count
    total_storage   = local.total_storage
    free_tier_limit = 200
  }
}
`
	return os.WriteFile("main.tf", []byte(content), 0644)
}
// Create block_volumes.tf
func (app *App) createTerraformBlockVolumes() error {
	printStatus("Creating block_volumes.tf...")

	if _, err := os.Stat("block_volumes.tf"); err == nil {
		backupName := fmt.Sprintf("block_volumes.tf.bak.%s", time.Now().Format("20060102_150405"))
		os.Rename("block_volumes.tf", backupName)
	}

	content := `# Block Volume Resources (Optional)
# Block volumes provide additional storage beyond boot volumes

# AMD Block Volumes
resource "oci_core_volume" "amd_block" {
  count = local.amd_block_volume_size_gb > 0 ? local.amd_micro_instance_count : 0

  compartment_id      = local.compartment_id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "${local.amd_micro_hostnames[count.index]}-block"
  size_in_gbs         = local.amd_block_volume_size_gb

  freeform_tags = {
    "Purpose" = "AlwaysFreeTier"
    "Type"    = "BlockVolume"
    "Managed" = "Terraform"
  }
}

resource "oci_core_volume_attachment" "amd_block" {
  count = local.amd_block_volume_size_gb > 0 ? local.amd_micro_instance_count : 0

  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.amd[count.index].id
  volume_id       = oci_core_volume.amd_block[count.index].id
}

# ARM Block Volumes, keyed by the original instance index.
resource "oci_core_volume" "arm_block" {
  for_each = { for index, size in local.arm_block_volume_sizes : tostring(index) => size if size > 0 }
  compartment_id      = local.compartment_id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "${local.arm_flex_hostnames[tonumber(each.key)]}-block"
  size_in_gbs         = each.value
  freeform_tags = {
    "Purpose" = "AlwaysFreeTier"
    "Type"    = "BlockVolume"
    "Managed" = "Terraform"
  }
}

resource "oci_core_volume_attachment" "arm_block" {
  for_each = oci_core_volume.arm_block
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.arm[tonumber(each.key)].id
  volume_id       = each.value.id
}
`

	return os.WriteFile("block_volumes.tf", []byte(content), 0644)
}

// Create cloud-init.yaml
func (app *App) createCloudInit() error {
	printStatus("Creating cloud-init.yaml...")

	if _, err := os.Stat("cloud-init.yaml"); err == nil {
		backupName := fmt.Sprintf("cloud-init.yaml.bak.%s", time.Now().Format("20060102_150405"))
		os.Rename("cloud-init.yaml", backupName)
	}

	content := `#cloud-config
hostname: ${hostname}
fqdn: ${hostname}.local
manage_etc_hosts: true

package_update: true
package_upgrade: true

packages:
  - curl
  - wget
  - git
  - htop
  - vim
  - unzip
  - jq
  - tmux
  - net-tools
  - iotop
  - ncdu

runcmd:
  - echo "Instance ${hostname} initialized at $(date)" >> /var/log/cloud-init-complete.log
  - systemctl enable --now fail2ban || true

# Basic security hardening
write_files:
  - path: /etc/ssh/sshd_config.d/hardening.conf
    content: |
      PermitRootLogin no
      PasswordAuthentication no
      MaxAuthTries 3
      ClientAliveInterval 300
      ClientAliveCountMax 2

timezone: UTC
ssh_pwauth: false

final_message: "Instance ${hostname} ready after $UPTIME seconds"
`

	return os.WriteFile("cloud-init.yaml", []byte(content), 0644)
}

// Helper functions
func buildArrayString(arr []string, quoted bool) string {
	if len(arr) == 0 {
		return "[]"
	}

	var builder strings.Builder
	builder.WriteString("[")
	for i, s := range arr {
		if i > 0 {
			builder.WriteString(", ")
		}
		if quoted {
			builder.WriteString(strconv.Quote(s))
		} else {
			builder.WriteString(s)
		}
	}
	builder.WriteString("]")
	return builder.String()
}

func buildArrayInt(arr []int) string {
	if len(arr) == 0 {
		return "[]"
	}

	var builder strings.Builder
	builder.WriteString("[")
	for i, v := range arr {
		if i > 0 {
			builder.WriteString(", ")
		}
		builder.WriteString(fmt.Sprintf("%d", v))
	}
	builder.WriteString("]")
	return builder.String()
}

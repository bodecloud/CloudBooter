# Go Implementation of OCI Terraform Setup

The Go command inventories OCI resources and generates Terraform for an IPv4 VCN, routes, security rules, subnet, and AMD/ARM instances. The ARM baseline is 2 OCPU / 12 GB with a combined 200 GB storage cap.

## Structure

All Go source files are in `cmd/setup-oci-terraform/`:

- `main.go` - Main entry point and CLI setup
- `oci_client.go` - OCI SDK client initialization and authentication
- `inventory.go` - Resource discovery and inventory
- `config.go` - Configuration management and user prompts
- `utils.go` - Utility functions (SSH keys, prompts, retries)
- `filegen.go` - Terraform file generation
- `terraform.go` - Terraform workflow execution

## Building

```bash
cd implementations/go
go mod download
go build -o setup-oci-terraform ./cmd/setup-oci-terraform
```

## Usage

Same as the bash script:
```bash
./setup-oci-terraform
./setup-oci-terraform --non-interactive --auto-deploy
```

## Dependencies

- github.com/oracle/oci-go-sdk/v65 - OCI SDK
- github.com/spf13/cobra - CLI framework
- golang.org/x/crypto/ssh - SSH key generation

## Validation

Saved configurations restore all CPU, memory, boot, and block-volume arrays. Invalid array lengths or allocations beyond the configured Always Free caps stop generation. Terraform generation also rejects a custom OCI config path, since the provider reads the standard `~/.oci/config` path. New ARM allocations reserve CPU, memory, and boot storage for later instances.

Run the repository's PowerShell static checks from the repository root:

```powershell
./implementations/tests/Test-LegacyImplementations.ps1
```

These checks inspect packaging, Go declarations/import usage, Terraform references, allocation guards, and retry handling. They do not compile Go, execute Python or Bash, contact OCI, or validate provider schemas. Build the Go command and validate a generated plan before relying on it for deployment.

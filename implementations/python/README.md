# Python Implementation

A standalone Python module for OCI Terraform setup. The default ARM allocation is 2 OCPU / 12 GB, matching the configured Always Free baseline.

## Features

- Full Python implementation with rich CLI output
- Package-based architecture
- Cross-platform support
- Type hints for better code clarity

## Installation

```bash
cd implementations/python
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install -e .
```

## Usage

### Basic Usage

```bash
python setup_oci_terraform.py
```

### As a Package

```bash
oci-terraform-setup
```

### Command Line Options

```bash
python setup_oci_terraform.py --help
```

Available options:
- `--non-interactive` - Run without prompts
- `--auto-use-existing` - Automatically use existing instances
- `--auto-deploy` - Automatically deploy
- `--force-reauth` - Force re-authentication
- `--debug` - Enable debug logging
- `--skip-config` - Restore saved configuration before deployment

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests (if available)
pytest

# Format code
black .

# Lint
flake8
```

## Project Structure

```
python/
├── setup_oci_terraform.py  # Main entry point
├── requirements.txt         # Dependencies
├── pyproject.toml          # Package configuration
├── setup.py                # Package setup
└── README.md               # This file
```

## See Also

- [Main README](../../README.md)
- [Free Tier Guide](../../docs/FREE_TIER.md)

The package installs the existing `setup_oci_terraform` module and exposes its `main` function as `oci-terraform-setup`. `--help` prints command options before prerequisites or provisioning run.

The shared PowerShell static checks live at `implementations/tests/Test-LegacyImplementations.ps1`. They check source invariants only; Python execution, package installation, Terraform provider validation, and cloud deployment require separate runtime checks.

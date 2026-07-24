"""Cloudflare prerequisite installer — wrangler (npm) + Terraform.

Mirrors GCP's 3-tier strategy:
  Tier 1: native package managers / npm global
  Tier 2: npx (no global install)
  Tier 3: CF_MODE=api (pure requests; no wrangler)

Refs:
  https://developers.cloudflare.com/workers/wrangler/install-and-update/
  https://releases.hashicorp.com/terraform/
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

TERRAFORM_RELEASES = "https://releases.hashicorp.com/terraform"


def _run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    kwargs: dict = {"check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)  # noqa: S603


def wrangler_on_path() -> bool:
    return shutil.which("wrangler") is not None


def terraform_on_path() -> bool:
    return shutil.which("terraform") is not None


def npm_on_path() -> bool:
    return shutil.which("npm") is not None or shutil.which("npx") is not None


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_linux() -> bool:
    return platform.system() == "Linux"


def install_wrangler() -> str:
    """Install wrangler CLI. Returns 'wrangler', 'npx', or 'api'."""
    if wrangler_on_path():
        return "wrangler"

    print("[cloudbooter] wrangler not found — attempting npm global install…")
    if npm_on_path() and shutil.which("npm"):
        r = _run(["npm", "install", "-g", "wrangler"], check=False)
        if r.returncode == 0 and wrangler_on_path():
            return "wrangler"

    if shutil.which("npx"):
        print("[cloudbooter] Falling back to npx wrangler (CF_MODE=npx).")
        return "npx"

    print(
        "[cloudbooter] WARNING: wrangler unavailable — switching to "
        "API-only mode (CF_MODE=api)."
    )
    return "api"


def install_terraform(version: str = "latest") -> bool:
    """Install Terraform if not present. Returns True on success."""
    if terraform_on_path():
        return True

    print("[cloudbooter] terraform not found — attempting auto-install…")

    if _is_windows() and shutil.which("winget"):
        args = [
            "winget", "install", "--id", "Hashicorp.Terraform", "--silent",
            "--accept-source-agreements", "--accept-package-agreements",
        ]
        if version != "latest":
            args += ["--version", version]
        r = _run(args, check=False)
        if r.returncode == 0:
            return True

    if _is_linux() and shutil.which("apt-get"):
        cmds = [
            "wget -O- https://apt.releases.hashicorp.com/gpg"
            " | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg",
            'echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg]'
            ' https://apt.releases.hashicorp.com $(lsb_release -cs) main"'
            " | sudo tee /etc/apt/sources.list.d/hashicorp.list",
            "sudo apt-get update -qq",
            "sudo apt-get install -y terraform",
        ]
        ok = True
        for cmd in cmds:
            r = subprocess.run(cmd, shell=True, check=False)  # noqa: S602
            if r.returncode != 0:
                ok = False
                break
        if ok and terraform_on_path():
            return True

    if _is_macos() and shutil.which("brew"):
        r = _run(["brew", "install", "hashicorp/tap/terraform"], check=False)
        if r.returncode == 0:
            return True

    return _install_terraform_zip(version)


def _resolve_terraform_version(requested: str) -> str:
    if requested != "latest":
        return requested
    try:
        with urllib.request.urlopen(
            "https://checkpoint-api.hashicorp.com/v1/check/terraform", timeout=10
        ) as resp:
            data = json.loads(resp.read())
            return data.get("current_version", "1.10.5")
    except Exception:  # noqa: BLE001
        return "1.10.5"


def _install_terraform_zip(version: str) -> bool:
    version = _resolve_terraform_version(version)
    system = platform.system().lower()
    machine = platform.machine().lower()

    arch_map = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    arch = arch_map.get(machine, "amd64")
    os_name = {"windows": "windows", "darwin": "darwin", "linux": "linux"}.get(system, "linux")
    binary = "terraform.exe" if os_name == "windows" else "terraform"

    url = f"{TERRAFORM_RELEASES}/{version}/terraform_{version}_{os_name}_{arch}.zip"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / f"terraform_{version}.zip"
            print(f"[cloudbooter] Downloading Terraform {version} from {url} …")
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extract(binary, tmp)
            src = Path(tmp) / binary
            if os_name == "windows":
                dst = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Terraform"
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst / binary)
                os.environ["PATH"] = str(dst) + os.pathsep + os.environ.get("PATH", "")
            else:
                dst = Path("/usr/local/bin") / binary
                try:
                    shutil.copy2(src, dst)
                    dst.chmod(0o755)
                except PermissionError:
                    _run(["sudo", "cp", str(src), str(dst)], check=False)
                    _run(["sudo", "chmod", "755", str(dst)], check=False)
        return terraform_on_path()
    except Exception as exc:  # noqa: BLE001
        print(f"[cloudbooter] Terraform zip install error: {exc}")
        return False


def ensure_python_deps(requirements_txt: str | None = None) -> None:
    """Pip-install required packages if not present."""
    packages = [
        "requests>=2.32.0",
        "click>=8.1.0",
        "rich>=13.0.0",
    ]
    if requirements_txt and Path(requirements_txt).exists():
        _run([sys.executable, "-m", "pip", "install", "-q", "-r", requirements_txt], check=False)
    else:
        _run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=False)

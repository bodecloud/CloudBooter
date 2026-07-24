"""cloudbooter-cloudflare CLI entrypoint.

Usage:
  cloudbooter-cloudflare deploy   [options]
  cloudbooter-cloudflare validate [options]
  cloudbooter-cloudflare inventory [options]
  cloudbooter-cloudflare install-deps
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click


@click.group()
@click.version_option("0.1.0", prog_name="cloudbooter-cloudflare")
def main() -> None:
    """CloudBooter Cloudflare — Free-plan provisioning toolkit."""


@main.command()
@click.option("--account-id", envvar="CLOUDFLARE_ACCOUNT_ID", required=True, help="Cloudflare account ID")
@click.option("--api-token", envvar="CLOUDFLARE_API_TOKEN", default="", help="Cloudflare API token")
@click.option("--worker-name", envvar="CLOUDFLARE_WORKER_NAME", default="cloudbooter-worker", show_default=True)
@click.option("--r2-bucket", envvar="CLOUDFLARE_R2_BUCKET", default="cloudbooter-r2", show_default=True)
@click.option("--d1-name", envvar="CLOUDFLARE_D1_NAME", default="cloudbooter-db", show_default=True)
@click.option("--kv-title", envvar="CLOUDFLARE_KV_TITLE", default="cloudbooter-kv", show_default=True)
@click.option("--workers-cpu-ms", envvar="CLOUDFLARE_WORKERS_CPU_MS", default=10, show_default=True, type=int)
@click.option("--r2-storage-class", envvar="CLOUDFLARE_R2_STORAGE_CLASS", default="Standard", show_default=True)
@click.option("--zone-id", envvar="CLOUDFLARE_ZONE_ID", default="")
@click.option("--allow-paid/--no-allow-paid", envvar="CLOUDFLARE_ALLOW_PAID_RESOURCES", default=False)
@click.option("--auto-deploy/--no-auto-deploy", envvar="AUTO_DEPLOY", default=False)
@click.option("--non-interactive/--interactive", envvar="NON_INTERACTIVE", default=False)
@click.option("--output-dir", default=".", show_default=True, help="Directory to write .tf files into")
def deploy(
    account_id,
    api_token,
    worker_name,
    r2_bucket,
    d1_name,
    kv_title,
    workers_cpu_ms,
    r2_storage_class,
    zone_id,
    allow_paid,
    auto_deploy,
    non_interactive,
    output_dir,
):
    """Generate Terraform files and optionally deploy."""
    from cloudbooter.free_tier import validate_proposed_config
    from cloudbooter.renderers import (
        render_provider,
        render_variables,
        render_main,
        render_worker_script,
    )

    errors = validate_proposed_config(
        workers_cpu_ms=workers_cpu_ms,
        r2_storage_class=r2_storage_class,
        allow_paid_resources=allow_paid,
    )
    hard_errors = [e for e in errors if e.startswith("ERROR:")]
    if hard_errors:
        for e in hard_errors:
            click.echo(click.style(e, fg="red"), err=True)
        sys.exit(1)
    for e in errors:
        if e.startswith("WARN:"):
            click.echo(click.style(e, fg="yellow"), err=True)

    if non_interactive and not (api_token or os.environ.get("CLOUDFLARE_API_TOKEN")):
        click.echo(
            click.style(
                "ERROR: NON_INTERACTIVE deploy requires CLOUDFLARE_API_TOKEN "
                "(Terraform provider needs it at apply time).",
                fg="red",
            ),
            err=True,
        )
        sys.exit(1)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "provider.tf").write_text(render_provider(), encoding="utf-8")
    (out / "variables.tf").write_text(
        render_variables(
            account_id=account_id,
            worker_name=worker_name,
            workers_cpu_ms=workers_cpu_ms,
            r2_bucket_name=r2_bucket,
            r2_storage_class=r2_storage_class,
            d1_database_name=d1_name,
            kv_namespace_title=kv_title,
            zone_id=zone_id,
            include_zone=bool(zone_id),
        ),
        encoding="utf-8",
    )
    (out / "main.tf").write_text(render_main(), encoding="utf-8")
    (out / "worker.mjs").write_text(render_worker_script(), encoding="utf-8")

    # Optional tfvars for token (not committed by default naming)
    if api_token:
        (out / "terraform.tfvars").write_text(
            f'cloudflare_api_token = "{api_token}"\n',
            encoding="utf-8",
        )

    click.echo(click.style(f"Terraform files written to {out.resolve()}", fg="green"))

    if auto_deploy:
        _terraform_deploy(out, non_interactive)


@main.command()
@click.option("--workers-cpu-ms", default=10, type=int)
@click.option("--r2-storage-class", default="Standard")
@click.option("--do-backend", default=None)
@click.option("--enable-load-balancer/--no-enable-load-balancer", default=False)
@click.option("--worker-count", default=1, type=int)
@click.option("--allow-paid/--no-allow-paid", envvar="CLOUDFLARE_ALLOW_PAID_RESOURCES", default=False)
def validate(workers_cpu_ms, r2_storage_class, do_backend, enable_load_balancer, worker_count, allow_paid):
    """Validate a proposed config against Free-plan limits."""
    from cloudbooter.free_tier import validate_proposed_config

    errors = validate_proposed_config(
        workers_cpu_ms=workers_cpu_ms,
        r2_storage_class=r2_storage_class,
        do_backend=do_backend,
        enable_load_balancer=enable_load_balancer,
        worker_count=worker_count,
        allow_paid_resources=allow_paid,
    )
    if not errors:
        click.echo(click.style("✓ Config is within Cloudflare Free plan limits.", fg="green"))
    else:
        for e in errors:
            color = "red" if e.startswith("ERROR") else "yellow"
            click.echo(click.style(e, fg=color))
        sys.exit(1 if any(e.startswith("ERROR") for e in errors) else 0)


@main.command()
@click.option("--account-id", envvar="CLOUDFLARE_ACCOUNT_ID", required=True)
@click.option("--api-token", envvar="CLOUDFLARE_API_TOKEN", default="")
def inventory(account_id, api_token):
    """Show existing Cloudflare resources in the account."""
    from cloudbooter.inventory import run_full_inventory, display_inventory_dashboard

    click.echo(f"Fetching inventory for account={account_id} …")
    inv = run_full_inventory(account_id, token=api_token or None)
    display_inventory_dashboard(inv, account_id)


@main.command("install-deps")
@click.option("--requirements", default=None, help="Path to requirements.txt")
def install_deps(requirements):
    """Install wrangler, Terraform, and Python dependencies."""
    from cloudbooter.installer import install_wrangler, install_terraform, ensure_python_deps

    mode = install_wrangler()
    click.echo(f"CF_MODE={mode}")

    ok = install_terraform()
    click.echo(f"Terraform: {'installed' if ok else 'FAILED'}")

    ensure_python_deps(requirements)
    click.echo("Python deps: installed")


def _terraform_deploy(tf_dir: Path, non_interactive: bool) -> None:
    import subprocess

    env = os.environ.copy()
    env["TF_IN_AUTOMATION"] = "1" if non_interactive else ""
    # Prefer env token over tfvars when set
    if env.get("CLOUDFLARE_API_TOKEN"):
        # Provider also accepts CLOUDFLARE_API_TOKEN natively in many versions;
        # ensure TF_VAR_ is set for our variable.
        env.setdefault("TF_VAR_cloudflare_api_token", env["CLOUDFLARE_API_TOKEN"])

    for cmd in [
        ["terraform", "init", "-input=false"],
        ["terraform", "plan", "-input=false", "-out=tfplan"],
        ["terraform", "apply", "-input=false", "tfplan"],
    ]:
        click.echo(f"$ {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=tf_dir, env=env, check=False)  # noqa: S603
        if r.returncode != 0:
            click.echo(click.style(f"terraform command failed: {' '.join(cmd)}", fg="red"), err=True)
            sys.exit(r.returncode)

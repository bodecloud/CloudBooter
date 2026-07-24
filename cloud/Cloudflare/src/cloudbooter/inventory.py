"""Cloudflare resource inventory — wrangler with REST API fallback.

Populates ResourceInventory before any Terraform generation.
All functions are idempotent and never create/modify resources.

Refs:
  https://developers.cloudflare.com/api/
  https://developers.cloudflare.com/workers/wrangler/commands/
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceInventory:
    workers: dict[str, Any] = field(default_factory=dict)
    kv_namespaces: dict[str, Any] = field(default_factory=dict)
    r2_buckets: dict[str, Any] = field(default_factory=dict)
    d1_databases: dict[str, Any] = field(default_factory=dict)
    queues: dict[str, Any] = field(default_factory=dict)
    pages_projects: dict[str, Any] = field(default_factory=dict)
    zones: dict[str, Any] = field(default_factory=dict)


def _wrangler(*args: str) -> list[dict] | dict | None:
    """Run a wrangler command returning JSON when possible. Returns None on failure."""
    wrangler = shutil.which("wrangler")
    if wrangler:
        cmd = [wrangler, *args]
    elif shutil.which("npx"):
        cmd = ["npx", "--yes", "wrangler", *args]
    else:
        return None

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
        if r.returncode != 0:
            return None
        # Some wrangler commands print non-JSON; tolerate that
        out = r.stdout.strip()
        if not out:
            return []
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"raw": out}
    except Exception:  # noqa: BLE001
        return None


def _api_get(path: str, token: str) -> dict | list | None:
    """GET Cloudflare API v4 path. Returns result payload or None."""
    try:
        import requests

        resp = requests.get(
            f"https://api.cloudflare.com/client/v4{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        data = resp.json()
        if not data.get("success"):
            return None
        return data.get("result")
    except Exception:  # noqa: BLE001
        return None


def run_full_inventory(account_id: str, token: str | None = None) -> ResourceInventory:
    """Populate a ResourceInventory for the given Cloudflare account."""
    inv = ResourceInventory()
    token = token or os.environ.get("CLOUDFLARE_API_TOKEN", "").strip() or None

    # Prefer REST API when token present (structured); wrangler as secondary
    if token and account_id:
        scripts = _api_get(f"/accounts/{account_id}/workers/scripts", token)
        if isinstance(scripts, list):
            for s in scripts:
                name = s.get("id") or s.get("name")
                if name:
                    inv.workers[name] = s

        kvs = _api_get(f"/accounts/{account_id}/storage/kv/namespaces", token)
        if isinstance(kvs, list):
            for ns in kvs:
                title = ns.get("title") or ns.get("id")
                if title:
                    inv.kv_namespaces[title] = ns

        buckets = _api_get(f"/accounts/{account_id}/r2/buckets", token)
        # R2 list shape: {"buckets": [...]} or list
        if isinstance(buckets, dict):
            for b in buckets.get("buckets", []):
                name = b.get("name")
                if name:
                    inv.r2_buckets[name] = b
        elif isinstance(buckets, list):
            for b in buckets:
                name = b.get("name")
                if name:
                    inv.r2_buckets[name] = b

        d1 = _api_get(f"/accounts/{account_id}/d1/database", token)
        if isinstance(d1, list):
            for db in d1:
                name = db.get("name") or db.get("uuid")
                if name:
                    inv.d1_databases[name] = db

        queues = _api_get(f"/accounts/{account_id}/queues", token)
        if isinstance(queues, list):
            for q in queues:
                name = q.get("queue_name") or q.get("name") or q.get("queue_id")
                if name:
                    inv.queues[name] = q

        pages = _api_get(f"/accounts/{account_id}/pages/projects", token)
        if isinstance(pages, list):
            for p in pages:
                name = p.get("name")
                if name:
                    inv.pages_projects[name] = p

        zones = _api_get("/zones", token)
        if isinstance(zones, list):
            for z in zones:
                if z.get("account", {}).get("id") == account_id or not account_id:
                    name = z.get("name")
                    if name:
                        inv.zones[name] = z

        return inv

    # Wrangler fallback (best-effort; many list commands are interactive/text)
    whoami = _wrangler("whoami")
    if whoami is not None:
        inv.workers["_wrangler_session"] = {"whoami": whoami}

    return inv


def display_inventory_dashboard(inv: ResourceInventory, account_id: str) -> None:
    """Print an OCI/GCP-style inventory dashboard to stdout."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        console.print(f"\n[bold cyan]╔══ Cloudflare Resource Inventory — {account_id} ══╗[/]")

        def _tbl(title: str, items: dict, cols: list[str]) -> None:
            if not items:
                console.print(f"  [dim]{title}:[/] (none)")
                return
            t = Table(title=title, show_header=True, header_style="bold cyan")
            for c in cols:
                t.add_column(c)
            for name, data in items.items():
                if not isinstance(data, dict):
                    t.add_row(name, str(data))
                    continue
                row = [name] + [str(data.get(c, "—")) for c in cols[1:]]
                t.add_row(*row)
            console.print(t)

        _tbl("Workers", inv.workers, ["name", "modified_on", "created_on"])
        _tbl("KV Namespaces", inv.kv_namespaces, ["title", "id"])
        _tbl("R2 Buckets", inv.r2_buckets, ["name", "creation_date"])
        _tbl("D1 Databases", inv.d1_databases, ["name", "uuid"])
        _tbl("Queues", inv.queues, ["name"])
        _tbl("Pages Projects", inv.pages_projects, ["name", "subdomain"])
        _tbl("Zones", inv.zones, ["name", "id", "status"])

        console.print("[bold cyan]╚══════════════════════════════════════════════╝[/]\n")

    except ImportError:
        print(f"\n=== Cloudflare Resource Inventory — {account_id} ===")
        print(f"  Workers:   {len(inv.workers)}")
        print(f"  KV:        {len(inv.kv_namespaces)}")
        print(f"  R2:        {len(inv.r2_buckets)}")
        print(f"  D1:        {len(inv.d1_databases)}")
        print(f"  Queues:    {len(inv.queues)}")
        print(f"  Pages:     {len(inv.pages_projects)}")
        print(f"  Zones:     {len(inv.zones)}")
        print("=" * 48)

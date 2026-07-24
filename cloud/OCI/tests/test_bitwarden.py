"""Tests for Bitwarden OCI account discovery."""
from __future__ import annotations

import json

from cloudbooter.bitwarden import (
    account_slug,
    dedupe_accounts,
    discover_oci_accounts,
    parse_bw_item,
    sort_accounts,
)


def _api_key_item(
    *,
    item_id: str = "id-1",
    name: str = "Oracle armandfcrouch",
    username: str = "armandfcrouch@example.com",
) -> dict:
    return {
        "id": item_id,
        "name": name,
        "login": {
            "username": username,
            "uris": ["https://cloud.oracle.com"],
        },
        "fields": [
            {"name": "tenancy_ocid", "value": "ocid1.tenancy.oc1..aaa"},
            {"name": "user_ocid", "value": "ocid1.user.oc1..bbb"},
            {"name": "fingerprint", "value": "aa:bb:cc:dd"},
            {"name": "region", "value": "us-phoenix-1"},
            {
                "name": "private_key",
                "value": "-----BEGIN RSA PRIVATE KEY-----\nKEY\n-----END RSA PRIVATE KEY-----",
            },
        ],
    }


class TestParseBwItem:
    def test_parses_cloud_oracle_login(self):
        item = _api_key_item()
        acct = parse_bw_item(item)
        assert acct is not None
        assert acct.auth_mode == "api_key"
        assert acct.slug == "armandfcrouch"
        assert acct.tenancy_ocid == "ocid1.tenancy.oc1..aaa"

    def test_ignores_unrelated_item(self):
        item = {
            "id": "x",
            "name": "GitHub",
            "login": {"username": "dev", "uris": ["https://github.com"]},
        }
        assert parse_bw_item(item) is None

    def test_console_only_classification(self):
        item = {
            "id": "c1",
            "name": "OCI Console",
            "login": {
                "username": "user@example.com",
                "uris": ["https://cloud.oracle.com"],
            },
        }
        acct = parse_bw_item(item)
        assert acct is not None
        assert acct.auth_mode == "console_only"

    def test_pem_from_notes(self):
        item = {
            "id": "n1",
            "name": "Oracle OCI",
            "login": {"username": "oci-user", "uris": ["https://cloud.oracle.com"]},
            "notes": "-----BEGIN RSA PRIVATE KEY-----\nNOTEKEY\n-----END RSA PRIVATE KEY-----",
            "fields": [
                {"name": "tenancy", "value": "ocid1.tenancy.oc1..aaa"},
                {"name": "user", "value": "ocid1.user.oc1..bbb"},
                {"name": "fingerprint", "value": "fp"},
                {"name": "region", "value": "us-ashburn-1"},
            ],
        }
        acct = parse_bw_item(item)
        assert acct is not None
        assert acct.auth_mode == "api_key"
        assert "NOTEKEY" in (acct.private_key_pem or "")


class TestAccountOrdering:
    def test_sort_armandfcrouch_first(self):
        a = parse_bw_item(_api_key_item(name="Other", username="other@example.com"))
        b = parse_bw_item(
            _api_key_item(name="Primary", username="armandfcrouch@example.com")
        )
        assert a is not None and b is not None
        ordered = sort_accounts([a, b], start_account="armandfcrouch")
        assert ordered[0].slug == "armandfcrouch"

    def test_account_slug_from_username(self):
        assert account_slug("Oracle", "armandfcrouch@mail.com") == "armandfcrouch"


class TestDedupeAccounts:
    def test_prefers_api_key_ready_duplicate(self):
        incomplete = parse_bw_item(
            {
                "id": "1",
                "name": "OCI",
                "login": {"username": "same@example.com", "uris": ["https://cloud.oracle.com"]},
            }
        )
        complete = parse_bw_item(
            _api_key_item(item_id="2", username="same@example.com")
        )
        assert incomplete is not None and complete is not None
        result = dedupe_accounts([incomplete, complete])
        assert len(result) == 1
        assert result[0].auth_mode == "api_key"


class TestDiscoverOciAccounts:
    def test_discovers_with_mock_runner(self):
        items = [
            _api_key_item(),
            {
                "id": "2",
                "name": "GitHub",
                "login": {"username": "dev", "uris": ["https://github.com"]},
            },
        ]

        class FakeProc:
            returncode = 0
            stdout = json.dumps(items)
            stderr = ""

        def runner(*_args, **_kwargs):
            return FakeProc()

        accounts = discover_oci_accounts(runner=runner, session="sess", skip_unlock_check=True)
        assert len(accounts) == 1
        assert accounts[0].slug == "armandfcrouch"


class TestPrepareBitwardenSession:
    def test_returns_existing_unlocked_session(self, monkeypatch):
        monkeypatch.setenv("BW_SESSION", "existing-session")
        monkeypatch.setattr(
            "cloudbooter.bitwarden.bw_status",
            lambda _session=None: {"status": "unlocked"},
        )
        from cloudbooter.bitwarden import prepare_bitwarden_session

        assert prepare_bitwarden_session() == "existing-session"

    def test_api_key_login_then_unlock(self, monkeypatch):
        calls: list[list[str]] = []

        def fake_run_bw(args, *, env=None):
            calls.append(args)
            class Proc:
                returncode = 0
                stdout = "new-session-key"
                stderr = ""
            return Proc()

        statuses = iter(
            [
                {"status": "unauthenticated"},
                {"status": "locked"},
                {"status": "unlocked"},
            ]
        )

        monkeypatch.setenv("BW_CLIENTID", "client")
        monkeypatch.setenv("BW_CLIENTSECRET", "secret")
        monkeypatch.setenv("BW_PASSWORD", "pw")
        monkeypatch.setattr("cloudbooter.bitwarden._run_bw", fake_run_bw)
        monkeypatch.setattr("cloudbooter.bitwarden.bw_status", lambda _s=None: next(statuses))

        from cloudbooter.bitwarden import prepare_bitwarden_session

        assert prepare_bitwarden_session() == "new-session-key"
        assert ["login", "--apikey"] in calls
        assert ["unlock", "--passwordenv", "BW_PASSWORD", "--raw"] in calls

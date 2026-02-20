"""
M365 Migration Validator — End-to-end readiness check.

Verifies all Microsoft 365 integration points before enabling M365_ENABLED.

Usage:
    python active/migration_validator.py
"""

import asyncio
import json
import os
import sys

# Add project paths for imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
sys.path.insert(0, _script_dir)
sys.path.insert(0, os.path.join(_project_root, "core", "Infrastructure"))

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class ValidationResult:
    """Tracks pass/fail/skip results for each check."""

    def __init__(self):
        self.results = []

    def passed(self, name: str, detail: str = ""):
        msg = f"  [PASS] {name}"
        if detail:
            msg += f" ({detail})"
        self.results.append(("PASS", msg))
        print(msg)

    def failed(self, name: str, detail: str = ""):
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" -- {detail}"
        self.results.append(("FAIL", msg))
        print(msg)

    def skipped(self, name: str, detail: str = ""):
        msg = f"  [SKIP] {name}"
        if detail:
            msg += f" -- {detail}"
        self.results.append(("SKIP", msg))
        print(msg)

    @property
    def pass_count(self):
        return sum(1 for s, _ in self.results if s == "PASS")

    @property
    def fail_count(self):
        return sum(1 for s, _ in self.results if s == "FAIL")

    @property
    def skip_count(self):
        return sum(1 for s, _ in self.results if s == "SKIP")

    @property
    def all_passed(self):
        return self.fail_count == 0


async def validate():
    """Run all validation checks."""
    v = ValidationResult()

    print("=" * 50)
    print("  M365 Migration Validator")
    print("=" * 50)
    print()

    # ── Check 1: Credentials file ────────────────────────────────────
    from m1_config import MICROSOFT_CREDENTIALS_PATH

    if os.path.exists(MICROSOFT_CREDENTIALS_PATH):
        try:
            with open(MICROSOFT_CREDENTIALS_PATH, "r") as f:
                creds = json.load(f)
            azure = creds.get("azure_ad_application", {})
            has_all = all([
                azure.get("client_id"),
                azure.get("tenant_id"),
                azure.get("client_secret"),
            ])
            if has_all:
                v.passed("Credentials file", MICROSOFT_CREDENTIALS_PATH)
            else:
                v.failed("Credentials file", "missing client_id/tenant_id/client_secret")
        except (json.JSONDecodeError, IOError) as exc:
            v.failed("Credentials file", str(exc))
    else:
        v.failed("Credentials file", f"not found at {MICROSOFT_CREDENTIALS_PATH}")

    # ── Check 2: Config completeness ─────────────────────────────────
    from m1_config import (
        M365_CLIENT_ID, M365_TENANT_ID, M365_CLIENT_SECRET,
        SHAREPOINT_SITE_ID, ONENOTE_NOTEBOOK_ID,
        ACTION_ITEMS_LIST_ID, IDEA_BOARD_LIST_ID,
        M365_TOKEN_CACHE_PATH,
    )

    required = {
        "M365_CLIENT_ID": M365_CLIENT_ID,
        "M365_TENANT_ID": M365_TENANT_ID,
        "M365_CLIENT_SECRET": M365_CLIENT_SECRET,
        "SHAREPOINT_SITE_ID": SHAREPOINT_SITE_ID,
    }
    missing = [k for k, val in required.items() if not val]
    if missing:
        v.failed("Required env vars", f"missing: {', '.join(missing)}")
        print("\n  Cannot continue without credentials. Fix and re-run.\n")
        return v
    else:
        v.passed("Required env vars", "all set")

    # ── Check 3: Token acquisition ───────────────────────────────────
    from graph_client import GraphClient
    from async_session_manager import get_session, get_file_session, close

    graph = None
    try:
        session = await get_session()
        graph = GraphClient(
            client_id=M365_CLIENT_ID,
            tenant_id=M365_TENANT_ID,
            client_secret=M365_CLIENT_SECRET,
            session=session,
            token_cache_path=M365_TOKEN_CACHE_PATH,
        )
        headers = await graph.get_auth_headers()
        if "Authorization" in headers:
            v.passed("Token acquisition")
        else:
            v.failed("Token acquisition", "no token returned")
    except Exception as exc:
        v.failed("Token acquisition", str(exc))
        print("\n  Cannot continue without auth. Fix and re-run.\n")
        await close()
        return v

    # ── Check 4: Persistent token cache ──────────────────────────────
    if os.path.exists(M365_TOKEN_CACHE_PATH):
        v.passed("Persistent token cache", M365_TOKEN_CACHE_PATH)
    else:
        v.failed("Persistent token cache", f"not written to {M365_TOKEN_CACHE_PATH}")

    # ── Check 5: SharePoint site access ──────────────────────────────
    try:
        site = await graph.get(f"{GRAPH_BASE}/sites/{SHAREPOINT_SITE_ID}")
        site_name = site.get("displayName", "unknown")
        v.passed("SharePoint site access", f"site: {site_name}")
    except Exception as exc:
        v.failed("SharePoint site access", str(exc))

    # ── Check 6: Action_Items list ───────────────────────────────────
    if ACTION_ITEMS_LIST_ID:
        try:
            lst = await graph.get(
                f"{GRAPH_BASE}/sites/{SHAREPOINT_SITE_ID}/lists/{ACTION_ITEMS_LIST_ID}"
            )
            v.passed("Action_Items list", f"name: {lst.get('displayName', '?')}")
        except Exception as exc:
            v.failed("Action_Items list", str(exc))
    else:
        v.skipped("Action_Items list", "ACTION_ITEMS_LIST_ID not configured")

    # ── Check 7: Idea_Board list ─────────────────────────────────────
    if IDEA_BOARD_LIST_ID:
        try:
            lst = await graph.get(
                f"{GRAPH_BASE}/sites/{SHAREPOINT_SITE_ID}/lists/{IDEA_BOARD_LIST_ID}"
            )
            v.passed("Idea_Board list", f"name: {lst.get('displayName', '?')}")
        except Exception as exc:
            v.failed("Idea_Board list", str(exc))
    else:
        v.skipped("Idea_Board list", "IDEA_BOARD_LIST_ID not configured")

    # ── Check 8: OneNote notebook ────────────────────────────────────
    if ONENOTE_NOTEBOOK_ID:
        try:
            nb = await graph.get(
                f"{GRAPH_BASE}/me/onenote/notebooks/{ONENOTE_NOTEBOOK_ID}"
            )
            v.passed("OneNote notebook", f"name: {nb.get('displayName', '?')}")
        except Exception as exc:
            v.failed("OneNote notebook", str(exc))
    else:
        v.skipped("OneNote notebook", "ONENOTE_NOTEBOOK_ID not configured")

    # ── Check 9: File download session ───────────────────────────────
    try:
        file_session = await get_file_session()
        read_timeout = file_session.timeout.read
        if read_timeout and read_timeout >= 300:
            v.passed("File download session", f"read_timeout={read_timeout}s")
        else:
            v.failed("File download session", f"read_timeout={read_timeout}s (expected >=300)")
    except Exception as exc:
        v.failed("File download session", str(exc))

    # ── Check 10: active/ module imports ─────────────────────────────
    modules = [
        "graph_client", "async_session_manager", "onenote_client",
        "onenote_html_sanitizer", "sharepoint_list_reader",
        "file_fetcher", "proactive_engine",
    ]
    import_failures = []
    for mod in modules:
        try:
            __import__(mod)
        except Exception as exc:
            import_failures.append(f"{mod}: {exc}")

    if not import_failures:
        v.passed("active/ module imports", f"all {len(modules)} modules OK")
    else:
        v.failed("active/ module imports", "; ".join(import_failures))

    # ── Cleanup ──────────────────────────────────────────────────────
    await close()

    # ── Summary ──────────────────────────────────────────────────────
    print()
    print("=" * 50)
    total = v.pass_count + v.fail_count + v.skip_count
    print(
        f"  Result: {v.pass_count}/{total} passed, "
        f"{v.fail_count} failed, {v.skip_count} skipped"
    )
    if v.all_passed:
        print("  Ready to enable M365: YES")
    else:
        print("  Ready to enable M365: NO (fix failures first)")
    print("=" * 50)

    return v


if __name__ == "__main__":
    result = asyncio.run(validate())
    sys.exit(0 if result.all_passed else 1)

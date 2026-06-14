"""Tests de non-régression pour les correctifs de sécurité.

Couvre :
- ``_validate_endpoint`` : anti-fuite du token Bearer (SSRF / exfiltration).
- ``resolve_secret`` : indirection ``${VAR}`` pour les tokens.
- ``mask_token`` : masquage à l'affichage.
- ``_check_sse_auth`` : comparaison constante du Bearer SSE.
- Mode lecture seule : wrapper ``mcp.tool``.
"""

from __future__ import annotations

import pytest

from pennylane_mcp.api import _validate_endpoint
from pennylane_mcp.dossier_manager import mask_token, resolve_secret
from pennylane_mcp.server import _check_sse_auth


# ─── _validate_endpoint ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://evil.com/steal",
        "http://evil.com",
        "//evil.com",
        "http://169.254.169.254/latest/meta-data/",
        "/me\r\nHost: evil.com",
        "/me\nX-Injected: 1",
        "/path\\to\\thing",
        "",
    ],
)
def test_validate_endpoint_rejects_unsafe(endpoint: str) -> None:
    with pytest.raises(ValueError):
        _validate_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "/me",
        "/ledger_accounts",
        "/customers/123",
        "/trial_balance",
        "/redirect?url=https://example.com",
    ],
)
def test_validate_endpoint_accepts_relative_paths(endpoint: str) -> None:
    assert _validate_endpoint(endpoint) == endpoint


# ─── resolve_secret ────────────────────────────────────────────────────────────


def test_resolve_secret_resolves_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PENNYLANE_TOKEN_TEST", "pl_real_secret_value")
    assert resolve_secret("${PENNYLANE_TOKEN_TEST}") == "pl_real_secret_value"


def test_resolve_secret_missing_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PENNYLANE_TOKEN_MISSING", raising=False)
    with pytest.raises(RuntimeError):
        resolve_secret("${PENNYLANE_TOKEN_MISSING}")


def test_resolve_secret_passes_through_literal_token() -> None:
    assert resolve_secret("pl_literal_token_abc123") == "pl_literal_token_abc123"


def test_resolve_secret_resolves_dollar_var_without_braces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PENNYLANE_TOKEN_TEST", "pl_real_secret_value")
    assert resolve_secret("$PENNYLANE_TOKEN_TEST") == "pl_real_secret_value"


@pytest.mark.parametrize("value", ["${PENNYLANE_TOKEN_TEST", "$PENNYLANE_TOKEN_TEST}"])
def test_resolve_secret_rejects_malformed_braces(value: str) -> None:
    assert resolve_secret(value) == value


# ─── mask_token ────────────────────────────────────────────────────────────────


def test_mask_token_never_reveals_full_token() -> None:
    token = "pl_abcdef123456xyz"
    masked = mask_token(token)
    assert token not in masked
    assert masked.startswith("pl_abc")
    assert masked.endswith("xyz")


def test_mask_token_short_token() -> None:
    assert mask_token("short") == "****"


# ─── _check_sse_auth ────────────────────────────────────────────────────────────


def test_check_sse_auth_matches_exactly() -> None:
    assert _check_sse_auth("Bearer secret-token", "Bearer secret-token") is True


@pytest.mark.parametrize(
    "auth_header",
    [
        "Bearer wrong-token",
        "Bearer secret-token-extra",
        "bearer secret-token",
        "",
        "secret-token",
    ],
)
def test_check_sse_auth_rejects_mismatch(auth_header: str) -> None:
    assert _check_sse_auth(auth_header, "Bearer secret-token") is False


# ─── Mode lecture seule ─────────────────────────────────────────────────────────


def test_readonly_mode_skips_non_readonly_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_READONLY", "true")

    import asyncio
    import importlib
    import pennylane_mcp.server as server_module

    importlib.reload(server_module)
    try:
        mcp = server_module.mcp

        @mcp.tool(
            name="test_read_only",
            annotations={"readOnlyHint": True},
        )
        async def _read_only_tool() -> str:
            return "ok"

        @mcp.tool(
            name="test_write_tool",
            annotations={"readOnlyHint": False},
        )
        async def _write_tool() -> str:
            return "ok"

        tool_names = {t.name for t in asyncio.run(mcp.list_tools())}
        assert "test_read_only" in tool_names
        assert "test_write_tool" not in tool_names
    finally:
        monkeypatch.delenv("MCP_READONLY", raising=False)
        importlib.reload(server_module)

"""Tests de non-régression pour les correctifs de sécurité (mono-société).

Couvre :
- ``_validate_endpoint`` : anti-fuite du token Bearer (SSRF / exfiltration).

La version mono-société n'expose qu'un seul token (via ``PENNYLANE_API_TOKEN``),
sans fichier ``dossiers.json`` ni gestion multi-dossiers : il n'y a donc ni
``resolve_secret`` (le token vit déjà dans l'environnement), ni ``mask_token``
(pas d'outil ``list_dossiers``), ni mode ``MCP_READONLY``. La protection clé
restante — empêcher l'envoi du token Bearer vers un hôte tiers — est assurée par
``_validate_endpoint`` et testée ci-dessous.
"""

from __future__ import annotations

import pytest

from pennylane_mcp.api import _validate_endpoint


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
        # Mono-société durcit la règle : tout '://' est rejeté, même dans une
        # query string (pas d'endpoint Pennylane légitime n'en contient).
        "/redirect?url=https://example.com",
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
    ],
)
def test_validate_endpoint_accepts_relative_paths(endpoint: str) -> None:
    assert _validate_endpoint(endpoint) == endpoint

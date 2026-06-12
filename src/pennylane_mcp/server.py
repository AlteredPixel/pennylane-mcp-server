#!/usr/bin/env python3
"""Serveur MCP Pennylane — Point d'entrée principal.

Serveur MCP (Model Context Protocol) pour l'API comptable Pennylane.
Conçu pour une société unique, il expose des outils couvrant :
  - Plan comptable (CRUD)
  - Journaux comptables
  - Écritures comptables (CRUD + lignes)
  - Lignes d'écriture (lettrage, analytique)
  - Balance générale
  - Exercices fiscaux
  - Clients (entreprises et particuliers)
  - Fournisseurs
  - Factures clients (CRUD, finalisation, paiement)
  - Factures fournisseurs (consultation, mise à jour, paiement)
  - Produits / services (catalogue)
  - Devis (CRUD, envoi par email, statut)
  - Catégories analytiques (groupes et catégories)
  - Exports comptables (FEC, Grand Livre Analytique)
  - Abonnements de facturation récurrente
  - Suivi des modifications (ChangeLogs)

Modes de transport :
  - stdio  : usage local (Claude Desktop, Claude Code) — par défaut
  - sse    : usage distant via URL — activé par MCP_TRANSPORT=sse (token requis)

Un fichier .env (répertoire courant ou parents) est chargé automatiquement
s'il existe, sans écraser les variables déjà définies dans l'environnement.

Variables d'environnement :
    PENNYLANE_API_TOKEN   — Token Bearer Company API Pennylane (obligatoire)
    MCP_TRANSPORT         — Transport : 'stdio' (défaut) ou 'sse'
    MCP_HOST              — Hôte d'écoute SSE (défaut: 127.0.0.1)
    MCP_PORT              — Port d'écoute SSE (défaut: 8000)
    MCP_AUTH_TOKEN        — Token d'authentification SSE (obligatoire en SSE)
"""

from __future__ import annotations

import hmac
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .api import close_client, init_client
from .constants import SERVER_NAME, SERVER_VERSION
from .tools import (
    accounts,
    billing_subscriptions,
    categories,
    changelogs,
    customer_invoices,
    customers,
    entries,
    entry_lines,
    exports,
    journals,
    me,
    products,
    quotes,
    supplier_invoices,
    suppliers,
    trial_balance,
)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Cycle de vie du serveur : initialisation du client Pennylane."""

    # Charge un fichier .env s'il existe (répertoire courant ou parents).
    # N'écrase jamais une variable déjà définie dans l'environnement
    # (ex: configurée explicitement via claude_desktop_config.json).
    load_dotenv(override=False)

    api_token = os.environ.get("PENNYLANE_API_TOKEN", "").strip()
    if not api_token:
        print(
            "❌ Variable PENNYLANE_API_TOKEN manquante.\n"
            "   Définissez votre token Company API Pennylane "
            "(Paramètres > Connectivité > Développeurs).",
            file=sys.stderr,
        )
        sys.exit(1)

    init_client(api_token)
    print(
        f"🚀 {SERVER_NAME} v{SERVER_VERSION} démarré",
        file=sys.stderr,
    )
    try:
        yield {}
    finally:
        await close_client()
        print(f"🛑 {SERVER_NAME} arrêté", file=sys.stderr)


# ─── Création du serveur ─────────────────────────────────────────────────────

mcp = FastMCP(
    SERVER_NAME,
    lifespan=lifespan,
)

# ─── Enregistrement de tous les outils ───────────────────────────────────────

me.register(mcp)
accounts.register(mcp)
journals.register(mcp)
entries.register(mcp)
entry_lines.register(mcp)
trial_balance.register(mcp)
customers.register(mcp)
suppliers.register(mcp)
customer_invoices.register(mcp)
supplier_invoices.register(mcp)
products.register(mcp)
quotes.register(mcp)
categories.register(mcp)
exports.register(mcp)
billing_subscriptions.register(mcp)
changelogs.register(mcp)


# ─── Point d'entrée ─────────────────────────────────────────────────────────


def main() -> None:
    """Démarre le serveur MCP.

    Le mode de transport est déterminé par la variable MCP_TRANSPORT :
      - 'stdio' (défaut) : communication locale via stdin/stdout
      - 'sse'            : serveur HTTP avec Server-Sent Events

    En mode SSE, le serveur écoute sur MCP_HOST:MCP_PORT (défaut 127.0.0.1:8000)
    et exige un token MCP_AUTH_TOKEN.
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()

    if transport == "sse":
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("MCP_PORT", "8000"))

        # Sécurité : en SSE, le serveur expose toute la comptabilité sur le
        # réseau. On REFUSE de démarrer sans token d'authentification, sinon
        # n'importe qui atteignant le port aurait un accès total.
        auth_token = os.environ.get("MCP_AUTH_TOKEN", "")
        if not auth_token:
            print(
                "❌ Mode SSE refusé : la variable MCP_AUTH_TOKEN est obligatoire.\n"
                "   Définissez un token secret (long et aléatoire) pour protéger\n"
                "   l'accès, ou utilisez le transport stdio (local) par défaut.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"🌐 {SERVER_NAME} v{SERVER_VERSION} — Mode SSE\n"
            f"   Écoute sur http://{host}:{port}/sse\n"
            f"   Utilisez un reverse proxy (Nginx) avec HTTPS en production.",
            file=sys.stderr,
        )
        import uvicorn
        mcp_app = mcp.sse_app()

        # Middleware reverse proxy + authentification
        class McpMiddleware:
            def __init__(self, app):
                self.app = app
            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    headers_dict = dict(scope.get("headers", []))
                    # Vérifier le token Bearer en temps constant (anti timing-
                    # attack). auth_token est garanti non vide ici (vérifié au
                    # démarrage). Décodage latin-1 tolérant pour éviter qu'un
                    # header malformé ne lève une exception.
                    auth_header = headers_dict.get(b"authorization", b"").decode("latin-1", errors="replace")
                    if not hmac.compare_digest(auth_header, f"Bearer {auth_token}"):
                        await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain")]})
                        await send({"type": "http.response.body", "body": b"Unauthorized"})
                        return
                    # Fix Host header pour Traefik
                    hdrs = [(k, b"localhost:8000" if k == b"host" else v) for k, v in scope.get("headers", [])]
                    scope = dict(scope, headers=hdrs)
                await self.app(scope, receive, send)

        mcp_app = McpMiddleware(mcp_app)
        uvicorn.run(mcp_app, host=host, port=port, log_level="info")
    else:
        print(
            f"🚀 {SERVER_NAME} v{SERVER_VERSION} — Mode stdio",
            file=sys.stderr,
        )
        mcp.run()


if __name__ == "__main__":
    main()

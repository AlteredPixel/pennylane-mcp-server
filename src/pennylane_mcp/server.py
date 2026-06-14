#!/usr/bin/env python3
"""Serveur MCP Pennylane — Point d'entrée principal.

Serveur MCP (Model Context Protocol) complet pour l'API comptable Pennylane.
Conçu pour les experts-comptables, il expose 80+ outils couvrant :
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
  - Gestion multi-dossiers (v2.0)

Modes de transport :
  - stdio  : usage local (Claude Desktop, Claude Code) — par défaut
  - sse    : usage distant via URL (Dust, site web) — activé par MCP_TRANSPORT=sse

Modes de fonctionnement :
  1. Multi-dossiers : fichier dossiers.json (recommandé pour les cabinets)
  2. Mono-dossier : variable PENNYLANE_API_TOKEN (rétrocompatibilité)

Variables d'environnement :
    PENNYLANE_API_TOKEN   — Token Bearer (mode mono-dossier)
    PENNYLANE_CONFIG_PATH — Chemin vers dossiers.json (optionnel)
    MCP_TRANSPORT         — Transport : 'stdio' (défaut) ou 'sse'
    MCP_HOST              — Hôte d'écoute SSE (défaut: 127.0.0.1)
    MCP_PORT              — Port d'écoute SSE (défaut: 8000)
    MCP_AUTH_TOKEN        — Token Bearer requis en mode SSE (obligatoire)
    MCP_READONLY          — 'true'/'1'/'yes' : n'expose que les outils de
                            consultation (readOnlyHint=True)
"""

from __future__ import annotations

import hmac
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from .api import close_client, init_client
from .constants import SERVER_NAME, SERVER_VERSION
from .dossier_manager import DossierManager, set_manager
from .tools import (
    accounts,
    billing_subscriptions,
    categories,
    changelogs,
    customer_invoices,
    customers,
    dossiers,
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


def _find_config_path() -> Path | None:
    """Recherche le fichier dossiers.json dans les emplacements habituels.

    Ordre de priorité :
    1. Variable d'environnement PENNYLANE_CONFIG_PATH
    2. Répertoire courant : ./dossiers.json
    3. Config utilisateur : ~/.config/pennylane-mcp/dossiers.json
    """
    # 1. Variable d'environnement explicite
    env_path = os.environ.get("PENNYLANE_CONFIG_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        # Le chemin est spécifié mais n'existe pas encore → on l'utilisera
        # pour la création par add_dossier
        return p

    # 2. Répertoire courant
    cwd = Path.cwd() / "dossiers.json"
    if cwd.exists():
        return cwd

    # 3. Config utilisateur
    home_config = Path.home() / ".config" / "pennylane-mcp" / "dossiers.json"
    if home_config.exists():
        return home_config

    return None


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Cycle de vie du serveur : initialisation multi-dossiers ou mono-dossier."""

    manager = None
    config_path = _find_config_path()

    # ── Tentative mode multi-dossiers ─────────────────────────────────────
    if config_path and config_path.exists():
        manager = DossierManager(config_path)
        loaded = await manager.load_config()

        if loaded and manager.has_dossiers():
            # Mode multi-dossiers activé
            await manager.init_all_clients()

            # Auto-sélection du premier dossier si aucun n'est défini
            if manager.current_slug is None:
                slugs = manager.list_slugs()
                if slugs:
                    await manager.switch_dossier(slugs[0])

            set_manager(manager)
            print(
                f"🚀 {SERVER_NAME} v{SERVER_VERSION} démarré — "
                f"Mode multi-dossiers ({manager.dossier_count} dossier(s), "
                f"actif: {manager.current_slug})",
                file=sys.stderr,
            )
            try:
                yield {}
            finally:
                await manager.close_all()
                print(f"🛑 {SERVER_NAME} arrêté", file=sys.stderr)
            return

    # ── Fallback : mode mono-dossier (rétrocompatibilité) ─────────────────
    api_token = os.environ.get("PENNYLANE_API_TOKEN", "")

    if not api_token:
        # Aucune configuration trouvée — créer un manager vide pour
        # permettre l'ajout dynamique de dossiers via les outils
        if config_path is None:
            # Définir un chemin par défaut pour la sauvegarde
            config_path = Path.cwd() / "dossiers.json"

        manager = DossierManager(config_path)
        set_manager(manager)

        print(
            f"🚀 {SERVER_NAME} v{SERVER_VERSION} démarré — "
            f"Mode initial (aucun dossier configuré).\n"
            f"   Utilisez pennylane_add_dossier pour ajouter un dossier,\n"
            f"   ou définissez PENNYLANE_API_TOKEN pour le mode mono-dossier.",
            file=sys.stderr,
        )
        try:
            yield {}
        finally:
            if manager.has_dossiers():
                await manager.close_all()
            print(f"🛑 {SERVER_NAME} arrêté", file=sys.stderr)
        return

    # Mode mono-dossier avec PENNYLANE_API_TOKEN
    # On crée quand même un DossierManager pour uniformiser l'accès
    if config_path is None:
        config_path = Path.cwd() / "dossiers.json"

    manager = DossierManager(config_path)
    await manager.add_dossier(
        slug="default",
        name="Dossier principal",
        token=api_token,
        save=False,  # Ne pas sauvegarder en mode legacy
    )
    set_manager(manager)

    print(
        f"🚀 {SERVER_NAME} v{SERVER_VERSION} démarré — Mode mono-dossier",
        file=sys.stderr,
    )
    try:
        yield {}
    finally:
        await manager.close_all()
        await close_client()
        print(f"🛑 {SERVER_NAME} arrêté", file=sys.stderr)


# ─── Création du serveur ─────────────────────────────────────────────────────

mcp = FastMCP(
    SERVER_NAME,
    lifespan=lifespan,
)


def _is_readonly_mode() -> bool:
    return os.environ.get("MCP_READONLY", "").strip().lower() in {"1", "true", "yes"}


if _is_readonly_mode():
    print(
        f"🔒 {SERVER_NAME} v{SERVER_VERSION} — Mode lecture seule "
        "(MCP_READONLY) : seuls les outils de consultation sont exposés.",
        file=sys.stderr,
    )
    _original_tool = mcp.tool

    def _readonly_tool(*args: object, **kwargs: object):
        annotations = kwargs.get("annotations") or {}
        if annotations.get("readOnlyHint") is True:
            return _original_tool(*args, **kwargs)

        def _noop_decorator(func):
            return func

        return _noop_decorator

    mcp.tool = _readonly_tool  # type: ignore[method-assign]


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
dossiers.register(mcp)  # Outils multi-dossiers (v2.0)


# ─── Authentification SSE ────────────────────────────────────────────────────


def _check_sse_auth(auth_header: str, expected: str) -> bool:
    """Vérifie le header ``Authorization`` en temps constant.

    Utilise ``hmac.compare_digest`` pour éviter les attaques par mesure de
    temps (timing attack) sur la comparaison du token.
    """
    return hmac.compare_digest(auth_header, expected)


# ─── Point d'entrée ─────────────────────────────────────────────────────────


def main() -> None:
    """Démarre le serveur MCP.

    Le mode de transport est déterminé par la variable MCP_TRANSPORT :
      - 'stdio' (défaut) : communication locale via stdin/stdout
      - 'sse'            : serveur HTTP avec Server-Sent Events

    En mode SSE, le serveur écoute sur MCP_HOST:MCP_PORT (défaut 127.0.0.1:8000).
    L'authentification est gérée par le middleware McpMiddleware (Bearer token).
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()

    if transport == "sse":
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("MCP_PORT", "8000"))
        print(
            f"🌐 {SERVER_NAME} v{SERVER_VERSION} — Mode SSE\n"
            f"   Écoute sur http://{host}:{port}/sse\n"
            f"   Utilisez un reverse proxy (Nginx) avec HTTPS en production.",
            file=sys.stderr,
        )
        import uvicorn
        from mcp.server.fastmcp import FastMCP
        mcp_app = mcp.sse_app()

        # Token d'authentification (obligatoire en SSE)
        auth_token = os.environ.get("MCP_AUTH_TOKEN", "")
        if not auth_token:
            print(
                "❌ MCP_AUTH_TOKEN est obligatoire en mode SSE "
                "(serveur exposé sur le réseau). Définissez cette variable "
                "avant de démarrer.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Middleware reverse proxy + authentification
        class McpMiddleware:
            def __init__(self, app):
                self.app = app
            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    headers_dict = dict(scope.get("headers", []))
                    auth_header = headers_dict.get(b"authorization", b"").decode("latin-1", errors="replace")
                    if not _check_sse_auth(auth_header, f"Bearer {auth_token}"):
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

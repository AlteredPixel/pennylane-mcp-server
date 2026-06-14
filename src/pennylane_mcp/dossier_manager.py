"""Gestionnaire multi-dossiers pour le serveur MCP Pennylane.

Gère un pool de clients httpx (un par dossier comptable), le dossier
actif, et la persistance dans un fichier ``dossiers.json``.

Chaque dossier possède son propre token Company API Pennylane.
Le manager est instancié une seule fois au démarrage du serveur et
accessible via ``get_manager()``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from .api import _validate_endpoint
from .constants import (
    API_BASE_URL,
    DOSSIER_CONFIG_VERSION,
    TOKEN_MIN_LENGTH,
)
from .models import DossierConfig, DossierInfo, DossiersFileSchema

# ─── Singleton global ─────────────────────────────────────────────────────────

_manager: Optional["DossierManager"] = None


def get_manager() -> "DossierManager":
    """Retourne l'instance globale du DossierManager."""
    if _manager is None:
        raise RuntimeError(
            "DossierManager non initialisé. "
            "Vérifiez que le serveur a démarré correctement."
        )
    return _manager


def set_manager(manager: "DossierManager") -> None:
    """Définit l'instance globale du DossierManager."""
    global _manager
    _manager = manager


def has_manager() -> bool:
    """Vérifie si le DossierManager est initialisé."""
    return _manager is not None


# ─── Utilitaires ──────────────────────────────────────────────────────────────


def mask_token(token: str) -> str:
    """Masque un token pour l'affichage sécurisé.

    Ex: 'pl_abc123def456xyz' → 'pl_abc…xyz'
    """
    if len(token) <= 8:
        return "****"
    return f"{token[:6]}…{token[-3:]}"


_SECRET_REF_RE = re.compile(r"^\$(?:(\w+)|\{(\w+)\})$")


def resolve_secret(value: str) -> str:
    """Résout une indirection ``${VAR}`` ou ``$VAR`` depuis l'environnement.

    Permet de stocker dans ``dossiers.json`` une référence vers une variable
    d'environnement plutôt que le token en clair. Si ``value`` ne correspond
    pas à ce motif, elle est renvoyée telle quelle (token littéral).

    Raises:
        RuntimeError: Si la variable d'environnement référencée est absente.
    """
    match = _SECRET_REF_RE.match(value)
    if not match:
        return value

    var_name = match.group(1) or match.group(2)
    resolved = os.environ.get(var_name)
    if resolved is None:
        raise RuntimeError(
            f"La variable d'environnement '{var_name}' référencée dans "
            "dossiers.json est introuvable. Définissez-la avant de démarrer "
            "le serveur."
        )
    return resolved


def _build_client(token: str) -> httpx.AsyncClient:
    """Crée un client httpx configuré pour l'API Pennylane.

    ``token`` peut être un token littéral ou une indirection ``${VAR}``
    résolue via :func:`resolve_secret` — le secret réel ne vit alors qu'en
    mémoire/environnement, jamais sur disque.
    """
    return httpx.AsyncClient(
        base_url=API_BASE_URL,
        timeout=30.0,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {resolve_secret(token)}",
            "X-Use-2026-API-Changes": "true",
        },
    )


# ─── DossierManager ──────────────────────────────────────────────────────────


class DossierManager:
    """Gère plusieurs dossiers Pennylane avec leurs clients HTTP respectifs.

    Attributes:
        _dossiers: Registre slug → DossierConfig.
        _clients: Pool slug → httpx.AsyncClient.
        _current_slug: Slug du dossier actuellement actif.
        _config_path: Chemin vers le fichier dossiers.json.
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._dossiers: dict[str, DossierConfig] = {}
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._current_slug: str | None = None
        self._config_path: Path | None = (
            Path(config_path) if config_path else None
        )

    # ── Propriétés ────────────────────────────────────────────────────────

    @property
    def current_slug(self) -> str | None:
        return self._current_slug

    @property
    def dossier_count(self) -> int:
        return len(self._dossiers)

    def has_dossiers(self) -> bool:
        return len(self._dossiers) > 0

    def list_slugs(self) -> list[str]:
        return list(self._dossiers.keys())

    # ── Chargement / sauvegarde config ────────────────────────────────────

    async def load_config(self) -> bool:
        """Charge dossiers.json. Retourne True si trouvé et chargé."""
        if self._config_path is None or not self._config_path.exists():
            return False

        try:
            mode = self._config_path.stat().st_mode
            if mode & 0o077:
                print(
                    f"⚠️  {self._config_path} est lisible par d'autres "
                    "utilisateurs du système. Ce fichier contient des "
                    "tokens API en clair : exécutez "
                    f"`chmod 600 {self._config_path}`.",
                    file=sys.stderr,
                )
        except OSError:
            pass

        try:
            raw = self._config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            schema = DossiersFileSchema.model_validate(data)

            for dc in schema.dossiers:
                self._dossiers[dc.slug] = dc

            if (
                schema.current_dossier
                and schema.current_dossier in self._dossiers
            ):
                self._current_slug = schema.current_dossier

            print(
                f"📁 {len(self._dossiers)} dossier(s) chargé(s) depuis "
                f"{self._config_path}",
                file=sys.stderr,
            )
            return True

        except Exception as exc:
            print(
                f"⚠️  Erreur chargement dossiers.json : {exc}",
                file=sys.stderr,
            )
            return False

    async def save_config(self) -> None:
        """Sauvegarde la configuration dans dossiers.json."""
        if self._config_path is None:
            return

        schema = DossiersFileSchema(
            version=DOSSIER_CONFIG_VERSION,
            current_dossier=self._current_slug,
            dossiers=list(self._dossiers.values()),
        )

        # Créer le répertoire parent si nécessaire
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        self._config_path.write_text(
            json.dumps(
                schema.model_dump(),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # Permissions restrictives (lecture/écriture propriétaire uniquement)
        try:
            os.chmod(self._config_path, 0o600)
        except OSError:
            pass  # Windows ou permissions insuffisantes

    # ── Gestion des clients ───────────────────────────────────────────────

    async def _ensure_client(self, slug: str) -> httpx.AsyncClient:
        """Crée le client httpx pour un dossier s'il n'existe pas encore."""
        if slug not in self._clients:
            if slug not in self._dossiers:
                raise RuntimeError(
                    f"Dossier '{slug}' introuvable dans la configuration."
                )
            self._clients[slug] = _build_client(self._dossiers[slug].token)
        return self._clients[slug]

    async def get_current_client(self) -> httpx.AsyncClient:
        """Retourne le client du dossier actif."""
        if self._current_slug is None:
            raise RuntimeError(
                "Aucun dossier actif. Utilisez pennylane_switch_dossier "
                "ou pennylane_add_dossier pour en sélectionner un."
            )
        return await self._ensure_client(self._current_slug)

    async def get_client(self, slug: str | None = None) -> httpx.AsyncClient:
        """Retourne le client pour un slug donné, ou le dossier actif."""
        target = slug or self._current_slug
        if target is None:
            raise RuntimeError(
                "Aucun dossier spécifié et aucun dossier actif."
            )
        return await self._ensure_client(target)

    # ── Opérations CRUD sur les dossiers ──────────────────────────────────

    async def add_dossier(
        self,
        slug: str,
        name: str,
        token: str,
        notes: str | None = None,
        *,
        save: bool = True,
    ) -> DossierConfig:
        """Ajoute un nouveau dossier au registre.

        Raises:
            ValueError: Si le slug existe déjà ou le token est trop court.
        """
        if slug in self._dossiers:
            raise ValueError(
                f"Le dossier '{slug}' existe déjà. "
                "Choisissez un autre identifiant."
            )
        if len(token) < TOKEN_MIN_LENGTH:
            raise ValueError(
                f"Le token doit contenir au moins {TOKEN_MIN_LENGTH} caractères."
            )

        config = DossierConfig(
            slug=slug,
            name=name,
            token=token,
            created_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )
        self._dossiers[slug] = config

        # Pré-créer le client
        self._clients[slug] = _build_client(token)

        # Auto-sélection si premier dossier
        if self._current_slug is None:
            self._current_slug = slug

        if save:
            await self.save_config()

        return config

    async def remove_dossier(self, slug: str) -> None:
        """Supprime un dossier du registre.

        Raises:
            ValueError: Si le slug n'existe pas.
        """
        if slug not in self._dossiers:
            raise ValueError(f"Dossier '{slug}' introuvable.")

        # Fermer le client associé
        if slug in self._clients:
            await self._clients[slug].aclose()
            del self._clients[slug]

        del self._dossiers[slug]

        # Si on supprime le dossier actif, basculer
        if self._current_slug == slug:
            if self._dossiers:
                self._current_slug = next(iter(self._dossiers))
            else:
                self._current_slug = None

        await self.save_config()

    async def switch_dossier(self, slug: str) -> DossierInfo:
        """Bascule vers un autre dossier.

        Raises:
            ValueError: Si le slug n'existe pas.
        """
        if slug not in self._dossiers:
            available = ", ".join(self._dossiers.keys()) or "(aucun)"
            raise ValueError(
                f"Dossier '{slug}' introuvable. "
                f"Dossiers disponibles : {available}"
            )

        self._current_slug = slug
        await self.save_config()
        return self._dossier_to_info(slug)

    # ── Consultation ──────────────────────────────────────────────────────

    def list_dossiers(self) -> list[DossierInfo]:
        """Liste tous les dossiers configurés (tokens masqués)."""
        return [
            self._dossier_to_info(slug) for slug in self._dossiers
        ]

    def get_current_info(self) -> DossierInfo | None:
        """Retourne les infos du dossier actif."""
        if self._current_slug is None:
            return None
        return self._dossier_to_info(self._current_slug)

    def get_dossier_name(self, slug: str) -> str | None:
        """Retourne le nom d'un dossier par son slug."""
        dc = self._dossiers.get(slug)
        return dc.name if dc else None

    # ── Requêtes parallèles ───────────────────────────────────────────────

    async def parallel_get(
        self,
        endpoint: str,
        slugs: list[str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Exécute un GET en parallèle sur plusieurs dossiers.

        Returns:
            dict[slug, {"data": ..., "error": None}] ou
            dict[slug, {"data": None, "error": "..."}]
        """
        results: dict[str, Any] = {}

        _validate_endpoint(endpoint)

        async def _fetch(slug: str) -> None:
            try:
                client = await self.get_client(slug)
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                results[slug] = {
                    "dossier": self.get_dossier_name(slug) or slug,
                    "data": resp.json(),
                    "error": None,
                }
            except Exception as exc:
                results[slug] = {
                    "dossier": self.get_dossier_name(slug) or slug,
                    "data": None,
                    "error": str(exc),
                }

        # Valider les slugs
        valid_slugs = []
        for s in slugs:
            if s in self._dossiers:
                valid_slugs.append(s)
            else:
                results[s] = {
                    "dossier": s,
                    "data": None,
                    "error": f"Dossier '{s}' introuvable.",
                }

        # Exécution parallèle
        await asyncio.gather(*[_fetch(s) for s in valid_slugs])
        return results

    # ── Cycle de vie ──────────────────────────────────────────────────────

    async def init_all_clients(self) -> None:
        """Initialise les clients pour tous les dossiers enregistrés."""
        for slug in self._dossiers:
            await self._ensure_client(slug)

    async def close_all(self) -> None:
        """Ferme tous les clients HTTP proprement."""
        for slug, client in self._clients.items():
            try:
                await client.aclose()
            except Exception:
                pass
        self._clients.clear()

    # ── Utilitaires internes ──────────────────────────────────────────────

    def _dossier_to_info(self, slug: str) -> DossierInfo:
        """Convertit un DossierConfig en DossierInfo (token masqué)."""
        dc = self._dossiers[slug]
        return DossierInfo(
            slug=dc.slug,
            name=dc.name,
            is_current=(slug == self._current_slug),
            created_at=dc.created_at,
            notes=dc.notes,
            token_masked=mask_token(dc.token),
        )

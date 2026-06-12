"""Client HTTP pour l'API Pennylane V2.

Gère l'authentification Bearer, les requêtes, et les messages d'erreur
actionnables en français.

**Mode multi-dossiers** : les fonctions ``api_get/post/put/delete``
acceptent un paramètre optionnel ``dossier_slug`` pour cibler un dossier
spécifique. Si omis, le dossier actif est utilisé.

Rétrocompatibilité totale : tous les appels existants sans
``dossier_slug`` continuent de fonctionner.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx

from .constants import API_BASE_URL

# ─── Validation des endpoints ────────────────────────────────────────────────

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _validate_endpoint(endpoint: str) -> str:
    """Valide qu'un endpoint est un chemin relatif sûr vers l'API Pennylane.

    Empêche toute fuite du token Bearer vers un hôte tiers : un endpoint
    absolu (``https://...``), protocole-relatif (``//evil.com``) ou contenant
    des caractères de contrôle (CRLF) serait sinon transmis tel quel à
    ``httpx``, qui le résoudrait comme une URL absolue (remplaçant
    ``base_url``) tout en conservant l'en-tête ``Authorization``.

    Raises:
        ValueError: Si l'endpoint n'est pas un chemin relatif valide.
    """
    if not endpoint:
        raise ValueError("Endpoint invalide : chaîne vide.")
    if _CONTROL_CHARS_RE.search(endpoint):
        raise ValueError("Endpoint invalide : caractères de contrôle interdits.")
    if "\\" in endpoint:
        raise ValueError("Endpoint invalide : antislash interdit.")
    if "://" in endpoint:
        raise ValueError("Endpoint invalide : schéma d'URL interdit.")
    if endpoint.startswith("//"):
        raise ValueError("Endpoint invalide : URL protocole-relative interdite.")
    if not endpoint.startswith("/"):
        raise ValueError("Endpoint invalide : doit commencer par '/'.")
    return endpoint

# ─── Legacy : client unique (rétrocompatibilité) ─────────────────────────────

_client: Optional[httpx.AsyncClient] = None


def init_client(api_token: str) -> None:
    """Initialise le client httpx legacy avec le token Bearer."""
    global _client
    _client = httpx.AsyncClient(
        base_url=API_BASE_URL,
        timeout=30.0,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
            "X-Use-2026-API-Changes": "true",
        },
    )


async def close_client() -> None:
    """Ferme proprement le client HTTP legacy."""
    global _client
    if _client:
        await _client.aclose()
        _client = None


# ─── Résolution du client (multi-dossier ou legacy) ──────────────────────────


async def _resolve_client(
    dossier_slug: str | None = None,
) -> httpx.AsyncClient:
    """Résout le client httpx à utiliser.

    Priorité :
    1. Si ``dossier_slug`` est fourni → client du dossier spécifié.
    2. Si le DossierManager est initialisé → client du dossier actif.
    3. Sinon → client legacy ``_client``.
    """
    # Import ici pour éviter les imports circulaires
    from .dossier_manager import get_manager, has_manager

    if has_manager():
        return await get_manager().get_client(dossier_slug)

    # Mode legacy
    if _client is None:
        raise RuntimeError(
            "Le client API n'est pas initialisé. "
            "Vérifiez la variable PENNYLANE_API_TOKEN ou le fichier dossiers.json."
        )
    return _client


# ─── Méthodes HTTP (multi-dossier) ───────────────────────────────────────────


async def api_get(
    endpoint: str,
    params: Optional[dict[str, Any]] = None,
    *,
    dossier_slug: Optional[str] = None,
) -> Any:
    """GET vers l'API Pennylane.

    Args:
        endpoint: Chemin API (ex: '/ledger_accounts').
        params: Paramètres de query string.
        dossier_slug: Slug du dossier cible (optionnel, défaut: dossier actif).
    """
    try:
        _validate_endpoint(endpoint)
        client = await _resolve_client(dossier_slug)
        resp = await client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc, dossier_slug) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            _prefix_dossier("Timeout : la requête vers Pennylane a expiré. Réessayez.", dossier_slug)
        ) from exc
    except httpx.ConnectError as exc:
        raise RuntimeError(
            _prefix_dossier("Connexion refusée : impossible de joindre l'API Pennylane.", dossier_slug)
        ) from exc


async def api_post(
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
    *,
    dossier_slug: Optional[str] = None,
) -> Any:
    """POST vers l'API Pennylane."""
    try:
        _validate_endpoint(endpoint)
        client = await _resolve_client(dossier_slug)
        resp = await client.post(endpoint, json=data)
        resp.raise_for_status()
        # Certains POST renvoient 204 ou un body vide (ex: send_by_email)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc, dossier_slug) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            _prefix_dossier("Timeout : requête expirée.", dossier_slug)
        ) from exc


async def api_put(
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
    *,
    dossier_slug: Optional[str] = None,
) -> Any:
    """PUT vers l'API Pennylane."""
    try:
        _validate_endpoint(endpoint)
        client = await _resolve_client(dossier_slug)
        resp = await client.put(endpoint, json=data)
        resp.raise_for_status()
        # Certains PUT renvoient 204 ou un body vide
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc, dossier_slug) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            _prefix_dossier("Timeout : requête expirée.", dossier_slug)
        ) from exc


async def api_delete(
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
    *,
    dossier_slug: Optional[str] = None,
) -> Any:
    """DELETE vers l'API Pennylane."""
    try:
        _validate_endpoint(endpoint)
        client = await _resolve_client(dossier_slug)
        resp = await client.request("DELETE", endpoint, json=data)
        resp.raise_for_status()
        # Certains DELETE renvoient 204 sans body
        if resp.status_code == 204:
            return {}
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc, dossier_slug) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            _prefix_dossier("Timeout : requête expirée.", dossier_slug)
        ) from exc


# ─── Requête parallèle multi-dossiers ────────────────────────────────────────


async def api_get_multi(
    endpoint: str,
    dossier_slugs: list[str],
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """GET en parallèle sur plusieurs dossiers.

    Args:
        endpoint: Chemin API.
        dossier_slugs: Liste des slugs à interroger.
        params: Paramètres de query string communs.

    Returns:
        dict[slug → {"dossier": name, "data": ..., "error": ...}]
    """
    from .dossier_manager import get_manager

    return await get_manager().parallel_get(endpoint, dossier_slugs, params)


# ─── Formatage des erreurs ────────────────────────────────────────────────────


def _prefix_dossier(msg: str, slug: str | None) -> str:
    """Préfixe un message d'erreur avec le nom du dossier si disponible."""
    if slug:
        return f"[{slug}] {msg}"
    return msg


def _format_error(
    exc: httpx.HTTPStatusError,
    dossier_slug: str | None = None,
) -> RuntimeError:
    """Transforme une erreur HTTP en message français actionnable."""
    status = exc.response.status_code
    try:
        body = exc.response.json()
    except Exception:
        body = {}

    msg = body.get("message") or body.get("error") or ""

    messages = {
        400: f"Requête invalide (400) : {msg or 'Vérifiez le format des données.'}",
        401: (
            "Authentification échouée (401) : token manquant, invalide ou expiré. "
            "Vérifiez le token du dossier."
        ),
        403: (
            f"Accès refusé (403) : {msg or 'Scopes insuffisants.'} "
            "Regénérez un token avec les bons scopes dans Pennylane."
        ),
        404: f"Ressource introuvable (404) : {msg or 'Vérifiez identifiant.'}",
        409: f"Conflit (409) : {msg or 'Doublon détecté.'}",
        422: f"Erreur de validation (422) : {msg or 'Données non conformes.'}",
        429: "Trop de requêtes (429) : attendez quelques secondes.",
    }

    text = messages.get(
        status,
        f"Erreur API Pennylane ({status}) : {msg or exc.response.text[:200]}",
    )
    return RuntimeError(_prefix_dossier(text, dossier_slug))

"""Client HTTP pour l'API Pennylane V2.

Gère l'authentification Bearer (un unique token Company API), les requêtes,
et des messages d'erreur actionnables en français.

Mode mono-société : le client est initialisé au démarrage du serveur à partir
de la variable d'environnement ``PENNYLANE_API_TOKEN``.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

from .constants import API_BASE_URL

# ─── Sécurité : validation des endpoints ─────────────────────────────────────


def _validate_endpoint(endpoint: str) -> str:
    """Garantit qu'un endpoint reste un chemin relatif sur l'API Pennylane.

    Avec httpx, une URL *absolue* (``https://hote/...``) ou *protocole-relative*
    (``//hote/...``) passée à ``client.get()`` **remplace** le ``base_url`` et
    envoie l'en-tête ``Authorization: Bearer <token>`` à un hôte arbitraire.
    Cette fonction empêche toute fuite du token vers un domaine tiers en
    n'autorisant que des chemins relatifs commençant par un unique ``/``.

    Raises:
        ValueError: Si l'endpoint pointe (ou pourrait pointer) hors de l'API.
    """
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError("Endpoint invalide : chaîne non vide attendue.")

    # Pas de caractères de contrôle (CRLF injection, etc.)
    if any(ord(c) < 0x20 for c in endpoint):
        raise ValueError("Endpoint invalide : caractères de contrôle interdits.")

    # Rejet d'un schéma explicite (http://, https://, file://, …)
    if "://" in endpoint:
        raise ValueError(
            "Endpoint invalide : seuls les chemins relatifs sont autorisés "
            "(pas d'URL absolue)."
        )

    # Doit commencer par '/' mais pas par '//' (protocole-relatif → autre hôte)
    if not endpoint.startswith("/") or endpoint.startswith("//"):
        raise ValueError(
            "Endpoint invalide : doit commencer par '/' et cibler l'API "
            "Pennylane (ex: '/ledger_accounts')."
        )

    # Les antislashs sont normalisés en '/' par certains clients → rejet.
    if "\\" in endpoint:
        raise ValueError("Endpoint invalide : antislash interdit.")
    # Défense supplémentaire : aucun schéma ni hôte ne doit subsister.
    parsed = urlsplit(endpoint)
    if parsed.scheme or parsed.netloc:
        raise ValueError("Endpoint invalide : schéma ou hôte interdit.")

    return endpoint


# ─── Client HTTP unique ──────────────────────────────────────────────────────

_client: Optional[httpx.AsyncClient] = None


def init_client(api_token: str) -> None:
    """Initialise le client httpx avec le token Bearer."""
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
    """Ferme proprement le client HTTP."""
    global _client
    if _client:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    """Retourne le client initialisé, ou lève une erreur explicite."""
    if _client is None:
        raise RuntimeError(
            "Le client API n'est pas initialisé. "
            "Vérifiez la variable d'environnement PENNYLANE_API_TOKEN."
        )
    return _client


# ─── Méthodes HTTP ───────────────────────────────────────────────────────────


async def api_get(
    endpoint: str,
    params: Optional[dict[str, Any]] = None,
) -> Any:
    """GET vers l'API Pennylane.

    Args:
        endpoint: Chemin API relatif (ex: '/ledger_accounts').
        params: Paramètres de query string.
    """
    try:
        endpoint = _validate_endpoint(endpoint)
        resp = await _get_client().get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "Timeout : la requête vers Pennylane a expiré. Réessayez."
        ) from exc
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Connexion refusée : impossible de joindre l'API Pennylane."
        ) from exc


async def api_post(
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
) -> Any:
    """POST vers l'API Pennylane."""
    try:
        endpoint = _validate_endpoint(endpoint)
        resp = await _get_client().post(endpoint, json=data)
        resp.raise_for_status()
        # Certains POST renvoient 204 ou un body vide (ex: send_by_email)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError("Timeout : requête expirée.") from exc


async def api_put(
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
) -> Any:
    """PUT vers l'API Pennylane."""
    try:
        endpoint = _validate_endpoint(endpoint)
        resp = await _get_client().put(endpoint, json=data)
        resp.raise_for_status()
        # Certains PUT renvoient 204 ou un body vide
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError("Timeout : requête expirée.") from exc


async def api_delete(
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
) -> Any:
    """DELETE vers l'API Pennylane."""
    try:
        endpoint = _validate_endpoint(endpoint)
        resp = await _get_client().request("DELETE", endpoint, json=data)
        resp.raise_for_status()
        # Certains DELETE renvoient 204 sans body
        if resp.status_code == 204:
            return {}
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise _format_error(exc) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError("Timeout : requête expirée.") from exc


# ─── Formatage des erreurs ────────────────────────────────────────────────────


def _format_error(exc: httpx.HTTPStatusError) -> RuntimeError:
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
            "Vérifiez PENNYLANE_API_TOKEN."
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

    return RuntimeError(
        messages.get(
            status,
            f"Erreur API Pennylane ({status}) : {msg or exc.response.text[:200]}",
        )
    )

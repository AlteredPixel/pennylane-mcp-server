"""Modèles Pydantic pour l'API Pennylane et les entrées des outils MCP."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════════════
#  Modèles de réponse API
# ═══════════════════════════════════════════════════════════════════════════════


class PaginatedResponse(BaseModel):
    """Enveloppe de réponse paginée standard Pennylane V2."""

    model_config = ConfigDict(extra="allow")

    total_pages: Optional[int] = None
    current_page: Optional[int] = None
    total_items: Optional[int] = None
    per_page: Optional[int] = None
    items: list[dict] = Field(default_factory=list)
    has_more: Optional[bool] = None
    next_cursor: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Entrées : Comptes comptables
# ═══════════════════════════════════════════════════════════════════════════════


class ListAccountsInput(BaseModel):
    """Paramètres pour lister les comptes du plan comptable."""

    model_config = ConfigDict(extra="forbid")

    cursor: Optional[str] = Field(
        default=None, description="Curseur pour la pagination."
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Nombre de résultats (1-1000, défaut: 50).",
    )
    number_prefix: Optional[str] = Field(
        default=None,
        description="Filtre par préfixe de numéro de compte "
        "(ex: '411' clients, '401' fournisseurs, '512' banque).",
    )
    enabled_only: bool = Field(
        default=True,
        description="Retourner uniquement les comptes actifs (défaut: true).",
    )
    sort: Optional[str] = Field(
        default=None, description="Tri: 'id' ou '-id'."
    )


class GetAccountInput(BaseModel):
    """Paramètres pour récupérer un compte comptable."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Identifiant unique du compte comptable.")


class CreateAccountInput(BaseModel):
    """Paramètres pour créer un compte comptable."""

    model_config = ConfigDict(extra="forbid")

    number: str = Field(
        ...,
        description="Numéro du compte (ex: '411001' client, '401001' fournisseur, '512000' banque). "
        "401→fournisseur auto-créé, 411→client auto-créé.",
    )
    label: str = Field(..., description="Libellé du compte comptable.")
    vat_rate: Optional[str] = Field(
        default=None,
        description="Taux de TVA (ex: 'FR_200' pour 20%, 'FR_100' pour 10%, 'exempt').",
    )
    country_alpha2: Optional[str] = Field(
        default=None, description="Code pays ISO alpha-2 (ex: 'FR'). Défaut: FR."
    )


class UpdateAccountInput(BaseModel):
    """Paramètres pour modifier un compte comptable."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Identifiant du compte à modifier.")
    label: Optional[str] = Field(
        default=None, description="Nouveau libellé du compte."
    )
    letterable: Optional[bool] = Field(
        default=None, description="Activer/désactiver le lettrage."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Entrées : Journaux
# ═══════════════════════════════════════════════════════════════════════════════


class ListJournalsInput(BaseModel):
    """Paramètres pour lister les journaux comptables."""

    model_config = ConfigDict(extra="forbid")

    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=50, ge=1, le=100, description="Résultats (1-100).")
    type_filter: Optional[str] = Field(
        default=None,
        description="Type de journal (sales, purchases, bank, payroll, miscellaneous).",
    )
    sort: Optional[str] = Field(default=None, description="Tri: 'id' ou '-id'.")


class GetJournalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Identifiant unique du journal.")


class CreateJournalInput(BaseModel):
    """Paramètres pour créer un journal comptable."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(
        ...,
        min_length=2,
        max_length=5,
        description="Code du journal (2-5 lettres). Ex: 'VE' ventes, 'HA' achats, 'BQ' banque, 'OD' opérations diverses.",
    )
    label: str = Field(..., description="Libellé du journal.")


# ═══════════════════════════════════════════════════════════════════════════════
#  Entrées : Écritures comptables
# ═══════════════════════════════════════════════════════════════════════════════


class EntryLineInput(BaseModel):
    """Ligne d'écriture comptable à créer."""

    model_config = ConfigDict(extra="forbid")

    ledger_account_id: int = Field(
        ..., description="ID du compte comptable pour cette ligne."
    )
    label: Optional[str] = Field(
        default=None, description="Libellé de la ligne d'écriture."
    )
    debit: str = Field(
        default="0", description="Montant au débit (string, ex: '1000.00')."
    )
    credit: str = Field(
        default="0", description="Montant au crédit (string, ex: '1000.00')."
    )
    piece_number: Optional[str] = Field(
        default=None, description="Numéro de pièce."
    )


class ListEntriesInput(BaseModel):
    """Paramètres pour lister les écritures comptables."""

    model_config = ConfigDict(extra="forbid")

    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=20, ge=1, le=100, description="Résultats (1-100).")
    journal_id: Optional[int] = Field(
        default=None, description="Filtrer par ID de journal."
    )
    date_from: Optional[str] = Field(
        default=None, description="Date de début (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        default=None, description="Date de fin (YYYY-MM-DD)."
    )
    sort: Optional[str] = Field(
        default=None, description="Tri: 'id', '-id', 'date', '-date'."
    )


class GetEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="Identifiant unique de l'écriture comptable.")


class CreateEntryInput(BaseModel):
    """Paramètres pour créer une écriture comptable."""

    model_config = ConfigDict(extra="forbid")

    date: str = Field(..., description="Date (YYYY-MM-DD).")
    label: str = Field(..., description="Libellé de l'écriture.")
    journal_id: int = Field(..., description="ID du journal comptable.")
    currency: str = Field(default="EUR", description="Code devise (défaut: EUR).")
    due_date: Optional[str] = Field(
        default=None, description="Date d'échéance (YYYY-MM-DD)."
    )
    piece_number: Optional[str] = Field(
        default=None, description="Numéro de pièce."
    )
    ledger_entry_lines: list[EntryLineInput] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Lignes d'écriture. TOTAL DÉBIT = TOTAL CRÉDIT obligatoire.",
    )


class EntryLineUpdateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="ID de la ligne existante.")
    label: Optional[str] = None
    debit: Optional[str] = None
    credit: Optional[str] = None
    ledger_account_id: Optional[int] = None


class UpdateEntryInput(BaseModel):
    """Paramètres pour modifier une écriture comptable."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Identifiant de l'écriture.")
    date: Optional[str] = Field(default=None, description="Nouvelle date.")
    label: Optional[str] = Field(default=None, description="Nouveau libellé.")
    journal_id: Optional[int] = Field(default=None, description="Nouvel ID journal.")
    currency: Optional[str] = Field(default=None, description="Nouvelle devise.")
    piece_number: Optional[str] = Field(default=None, description="N° pièce.")
    lines_to_create: Optional[list[EntryLineInput]] = Field(
        default=None, description="Nouvelles lignes à ajouter."
    )
    lines_to_update: Optional[list[EntryLineUpdateItem]] = Field(
        default=None, description="Lignes existantes à modifier."
    )
    lines_to_delete: Optional[list[int]] = Field(
        default=None, description="IDs des lignes à supprimer."
    )


class ListEntryLinesForEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_entry_id: int = Field(..., description="ID de l'écriture comptable.")
    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=50, ge=1, le=100, description="Résultats (1-100).")


# ═══════════════════════════════════════════════════════════════════════════════
#  Entrées : Lignes d'écriture (globales)
# ═══════════════════════════════════════════════════════════════════════════════


class ListAllEntryLinesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=20, ge=1, le=100, description="Résultats (1-100).")
    journal_id: Optional[int] = Field(default=None, description="Filtre par journal.")
    ledger_account_id: Optional[int] = Field(
        default=None, description="Filtre par compte."
    )
    date_from: Optional[str] = Field(default=None, description="Date début (YYYY-MM-DD).")
    date_to: Optional[str] = Field(default=None, description="Date fin (YYYY-MM-DD).")
    sort: Optional[str] = Field(default=None, description="Tri: 'id', '-id'.")


class GetEntryLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="ID de la ligne d'écriture.")


class LetterLinesInput(BaseModel):
    """Paramètres pour lettrer des lignes d'écriture."""

    model_config = ConfigDict(extra="forbid")

    line_ids: list[int] = Field(
        ...,
        min_length=2,
        description="IDs des lignes à lettrer (min 2, même compte, équilibrées).",
    )
    allow_partial: bool = Field(
        default=False,
        description="Autoriser le lettrage partiel (déséquilibré).",
    )


class UnletterLinesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_ids: list[int] = Field(
        ..., min_length=1, description="IDs des lignes à délettrer."
    )
    strategy: str = Field(
        default="none",
        description="'none' (erreur si déséquilibre) ou 'partial' (autorisé).",
    )


class CategoryWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(..., description="ID de la catégorie analytique.")
    weight: str = Field(
        default="1",
        description="Poids (0 à 1, ex: '0.5' pour 50%). Somme = 1.",
    )


class LinkCategoriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: int = Field(..., description="ID de la ligne d'écriture.")
    categories: list[CategoryWeight] = Field(
        ..., min_length=1, description="Catégories analytiques avec poids."
    )


class ListLineCategoriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: int = Field(..., description="ID de la ligne d'écriture.")
    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=50, ge=1, le=100, description="Résultats.")


class ListLetteredLinesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_id: int = Field(..., description="ID de la ligne de référence.")
    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=50, ge=1, le=100, description="Résultats.")


# ═══════════════════════════════════════════════════════════════════════════════
#  Entrées : Balance & Exercices
# ═══════════════════════════════════════════════════════════════════════════════


class GetTrialBalanceInput(BaseModel):
    """Paramètres pour récupérer la balance générale."""

    model_config = ConfigDict(extra="forbid")

    period_start: str = Field(
        ..., description="Début de période (YYYY-MM-DD)."
    )
    period_end: str = Field(
        ..., description="Fin de période (YYYY-MM-DD)."
    )
    is_auxiliary: Optional[bool] = Field(
        default=None,
        description="Filtre sur le type de compte : "
        "true = uniquement les comptes auxiliaires (détail par tiers 411xxx/401xxx), "
        "false = uniquement les comptes généraux, "
        "Ne pas renseigner (None) = tous les comptes retournés par l'API. "
        "Par défaut None : l'API retourne TOUS les comptes (classes 1 à 7), "
        "le serveur exclut automatiquement les auxiliaires de l'output sauf demande explicite.",
    )
    # Note : avec le header X-Use-2026-API-Changes: true, l'endpoint
    # /trial_balance utilise la pagination par curseur (limit + cursor +
    # has_more + next_cursor). La pagination est gérée automatiquement
    # par le tool (toutes les pages sont récupérées).


class ListFiscalYearsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cursor: Optional[str] = Field(default=None, description="Curseur.")
    limit: int = Field(default=20, ge=1, le=100, description="Résultats (1-100).")
    sort: Optional[str] = Field(
        default=None, description="Tri: 'id', '-id', 'start', '-start'."
    )


# Contexte Projet : Serveur MCP Pennylane (mono-société)

## Vue d'ensemble

Serveur **MCP** (Model Context Protocol) en **Python / FastMCP** connectant un LLM à l'API comptable **Pennylane V2**. Pilote **un seul dossier Pennylane** (une société), configuré via un unique token `PENNYLANE_API_TOKEN`.

**v3.0** : retrait complet du multi-dossiers — un serveur = une société = un token.

## Contexte métier : Pennylane

Pennylane est une plateforme de comptabilité collaborative française. Elle centralise saisie comptable, facturation, banque et collaboration entreprise/expert-comptable.

### Concepts comptables clés

- **Plan Comptable Général (PCG)** : comptes normalisés par classe (1=capitaux, 2=immobilisations, 3=stocks, 4=tiers, 5=financier, 6=charges, 7=produits). Préfixes importants : 401=fournisseurs, 411=clients, 421=personnel, 44=TVA/État, 512=banque, 530=caisse.

- **Journaux** : registres par nature (VE=ventes, HA=achats, BQ=banque, OD=opérations diverses, PA=paie).

- **Écriture comptable** : pièce composée de lignes équilibrées (total débits = total crédits), chaque ligne imputée sur un compte du PCG.

- **Lettrage** : rapprochement facture/règlement sur un même compte tiers. Permet le suivi des impayés.

- **Balance générale** : synthèse de tous les comptes avec soldes débit/crédit sur une période. Outil de contrôle essentiel.

- **Exercice fiscal** : période comptable (12 mois), statuts possibles : ouvert, clôturé, gelé, réouvert.

- **Comptabilité analytique** : ventilation charges/produits par catégories avec poids (somme = 1).

## Architecture technique

### API Pennylane V2

- **Base URL** : `https://app.pennylane.com/api/external/v2` (codée en dur, seule destination réseau)
- **Auth** : Bearer token (un unique token Company API)
- **Pagination** : curseur (`cursor` + `limit` + `has_more` + `next_cursor`)
- **Filtres** : JSON array `[{field, operator, value}]`
- **Scopes** : permissions granulaires (`ledger_accounts:all`, `journals:readonly`, etc.)

### Mode de fonctionnement

Unique : le client httpx est initialisé au démarrage à partir de `PENNYLANE_API_TOKEN`. Sans ce token, le serveur refuse de démarrer.

### Outils MCP

| Domaine | Outils | Fichier |
|---------|--------|---------|
| Connexion | `pennylane_whoami` | `tools/me.py` |
| Comptes | `list_accounts`, `get_account`, `create_account`, `update_account` | `tools/accounts.py` |
| Journaux | `list_journals`, `get_journal`, `create_journal` | `tools/journals.py` |
| Écritures | `list_entries`, `get_entry`, `create_entry`, `update_entry`, `list_entry_lines` | `tools/entries.py` |
| Lignes | `list_all_entry_lines`, `get_entry_line`, `letter_lines`, `unletter_lines`, `link_categories`, `list_line_categories`, `list_lettered_lines` | `tools/entry_lines.py` |
| Balance | `get_trial_balance`, `list_fiscal_years` | `tools/trial_balance.py` |

### Structure du code

```
src/pennylane_mcp/
├── server.py            — FastMCP + lifespan (init du client depuis PENNYLANE_API_TOKEN)
├── constants.py         — API_BASE_URL, CHARACTER_LIMIT, limites
├── models.py            — modèles Pydantic (entrées des outils)
├── api.py               — Client httpx async (api_get/post/put/delete + _validate_endpoint)
├── utils.py             — truncate_if_needed, pagination_summary, to_json
└── tools/               — modules métier, chacun avec register(mcp)
    ├── me.py            — pennylane_whoami
    ├── accounts.py      — comptes
    ├── journals.py      — journaux
    ├── entries.py       — écritures
    ├── entry_lines.py   — lignes (lettrage, analytique)
    ├── trial_balance.py — balance + exercices
    └── …                — customers, suppliers, invoices, quotes, products,
                            categories, exports, billing_subscriptions, changelogs
```

### Choix techniques

1. **Python + FastMCP** : framework MCP officiel, décorateurs `@mcp.tool`
2. **Pydantic v2** : validation stricte des entrées (`extra="forbid"`, contraintes `ge/le/min_length`)
3. **httpx async** : requêtes HTTP non-bloquantes avec timeout 30s
4. **Client unique** : initialisé au démarrage depuis `PENNYLANE_API_TOKEN`
5. **Sécurité endpoints** : `api._validate_endpoint` rejette toute URL absolue/protocole-relative pour empêcher la fuite du token Bearer vers un hôte tiers
6. **Erreurs en français** : messages actionnables
7. **Transport stdio** (défaut, local) ou **SSE** (distant, `MCP_AUTH_TOKEN` obligatoire)

## Cas d'usage

### Travaux courants
- Consultation / recherche dans le plan comptable
- Saisie d'écritures de journal (OD, à-nouveaux, corrections)
- Vérification de la balance par période
- Lettrage factures / règlements

### Travaux de clôture
- Revue de la balance et soldes anormaux
- Écritures de régularisation (provisions, amortissements, CCA, FNP)
- Vérification équilibre débit/crédit

### Analyse
- Mouvements d'un compte sur une période
- Suivi créances clients non lettrées (impayés)
- Ventilation analytique des charges

## Vision : Plateforme MCP multi-serveurs

Ce serveur est la brique fondatrice d'une **plateforme en ligne** :

```
Client LLM (API Claude, OpenAI, Mistral...)
       ↕ REST / WebSocket
   MCP Gateway Platform (multi-tenant)
       ↕ MCP Protocol
┌──────────────────────────────────┐
│ Pennylane MCP Server             │
│ Open Banking MCP Server          │
│ URSSAF MCP Server                │
│ Impots.gouv MCP Server           │
│ DSN / Paie MCP Server            │
└──────────────────────────────────┘
```

Pour passer en mode plateforme : changer `mcp.run()` en `mcp.run(transport="streamable_http", port=8000)`.

## Dépendances

- `mcp[cli]` >= 1.6.0 — SDK MCP officiel avec FastMCP
- `httpx` >= 0.27.0 — Client HTTP async
- `pydantic` >= 2.0.0 — Validation

## Comment étendre

1. Créer un modèle Pydantic dans `models.py`
2. Créer/enrichir un fichier dans `tools/`
3. Utiliser `@mcp.tool(name=..., annotations=...)` avec le modèle en paramètre
4. Appeler `register(mcp)` dans `server.py`

## Variables d'environnement

| Variable | Requis | Description |
|----------|--------|-------------|
| `PENNYLANE_API_TOKEN` | **Oui** | Token Bearer Company API Pennylane V2 |
| `MCP_TRANSPORT` | Non | `stdio` (défaut) ou `sse` |
| `MCP_HOST` / `MCP_PORT` | Non | Écoute SSE (défaut `127.0.0.1:8000`) |
| `MCP_AUTH_TOKEN` | En SSE | Token d'authentification, obligatoire en mode SSE |

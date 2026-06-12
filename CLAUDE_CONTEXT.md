# Contexte Projet : Serveur MCP Pennylane pour Expert-Comptable

## Vue d'ensemble

Serveur **MCP** (Model Context Protocol) en **Python / FastMCP** connectant un LLM à l'API comptable **Pennylane V2**. Destiné aux **experts-comptables** pour automatiser leurs opérations quotidiennes via un assistant IA.

**v2.0** : support multi-dossiers — gestion de plusieurs dossiers comptables simultanément, requêtes parallèles, et configuration dynamique.

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

- **Dossier comptable** : un dossier = une société/entreprise dans Pennylane. Un cabinet gère typiquement des dizaines de dossiers.

## Architecture technique

### API Pennylane V2

- **Base URL** : `https://app.pennylane.com/api/external/v2`
- **Auth** : Bearer token (un token Company API par dossier)
- **Pagination** : curseur (`cursor` + `limit` + `has_more` + `next_cursor`)
- **Filtres** : JSON array `[{field, operator, value}]`
- **Scopes** : permissions granulaires (`ledger_accounts:all`, `journals:readonly`, etc.)

### Modes de fonctionnement

1. **Multi-dossiers** (recommandé) : fichier `dossiers.json` avec N dossiers, chacun avec son token. Pool de clients httpx, switch à la volée, requêtes parallèles.
2. **Mono-dossier** (rétrocompatible) : variable `PENNYLANE_API_TOKEN`, crée un dossier "default" dans le manager.
3. **Mode initial** : ni fichier ni token, le serveur démarre vide et attend l'ajout d'un dossier via outil MCP.

### 28 outils MCP

| Domaine | Outils | Fichier |
|---------|--------|---------|
| Multi-dossiers | `list_dossiers`, `current_dossier`, `switch_dossier`, `add_dossier`, `remove_dossier`, `multi_dossier_query` | `tools/dossiers.py` |
| Connexion | `pennylane_whoami` | `tools/me.py` |
| Comptes | `list_accounts`, `get_account`, `create_account`, `update_account` | `tools/accounts.py` |
| Journaux | `list_journals`, `get_journal`, `create_journal` | `tools/journals.py` |
| Écritures | `list_entries`, `get_entry`, `create_entry`, `update_entry`, `list_entry_lines` | `tools/entries.py` |
| Lignes | `list_all_entry_lines`, `get_entry_line`, `letter_lines`, `unletter_lines`, `link_categories`, `list_line_categories`, `list_lettered_lines` | `tools/entry_lines.py` |
| Balance | `get_trial_balance`, `list_fiscal_years` | `tools/trial_balance.py` |

### Structure du code

```
src/pennylane_mcp/
├── server.py            — FastMCP + lifespan multi-mode (dossiers.json / PENNYLANE_API_TOKEN / vide)
├── constants.py         — API_BASE_URL, CHARACTER_LIMIT, constantes multi-dossiers
├── models.py            — 27+ modèles Pydantic (entrées outils + DossierConfig/Info)
├── api.py               — Client httpx async (api_get/post/put/delete + dossier_slug optionnel + api_get_multi)
├── utils.py             — truncate_if_needed, pagination_summary, to_json
├── dossier_manager.py   — DossierManager : pool de clients, switch, CRUD dossiers, requêtes parallèles
└── tools/               — 7 modules, chacun avec register(mcp)
    ├── dossiers.py      — 6 outils gestion multi-dossiers
    ├── me.py            — pennylane_whoami
    ├── accounts.py      — 4 outils comptes
    ├── journals.py      — 3 outils journaux
    ├── entries.py       — 5 outils écritures
    ├── entry_lines.py   — 7 outils lignes (lettrage, analytique)
    └── trial_balance.py — 2 outils balance + exercices
```

### Choix techniques

1. **Python + FastMCP** : framework MCP officiel, décorateurs `@mcp.tool`
2. **Pydantic v2** : validation stricte des entrées (`extra="forbid"`, contraintes `ge/le/min_length`)
3. **httpx async** : requêtes HTTP non-bloquantes avec timeout 30s
4. **Lifespan multi-mode** : détection auto du mode (dossiers.json → PENNYLANE_API_TOKEN → vide)
5. **DossierManager** : singleton gérant un pool de clients httpx, un par dossier, avec masquage des tokens
6. **Rétrocompatibilité** : `api_get/post/put/delete` acceptent un `dossier_slug` optionnel en keyword-only
7. **Requêtes parallèles** : `api_get_multi()` et `DossierManager.parallel_get()` via `asyncio.gather()`
8. **Erreurs en français** : messages actionnables, préfixés par le nom du dossier si applicable
9. **Transport stdio** : intégration locale (Claude Desktop). Passable en HTTP pour la plateforme.

### Configuration multi-dossiers (dossiers.json)

```json
{
  "version": "1.0",
  "current_dossier": "sarl-dupont",
  "dossiers": [
    {
      "slug": "sarl-dupont",
      "name": "SARL Dupont",
      "token": "pl_xxx...",
      "created_at": "2025-02-10T12:00:00Z",
      "notes": "Client principal"
    }
  ]
}
```

Recherche du fichier : `PENNYLANE_CONFIG_PATH` env → `./dossiers.json` → `~/.config/pennylane-mcp/dossiers.json`.

## Cas d'usage expert-comptable

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

### Multi-dossiers (nouveau v2.0)
- Basculer entre dossiers clients à la volée
- Comparer des balances entre plusieurs clients
- Ajouter/supprimer des dossiers sans relancer le serveur
- Requêtes parallèles pour consolider des données

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
| `PENNYLANE_API_TOKEN` | Non* | Token Bearer API Pennylane V2 (mode mono-dossier) |
| `PENNYLANE_CONFIG_PATH` | Non | Chemin vers dossiers.json |
| `MCP_TRANSPORT` | Non | `stdio` (défaut) ou `sse` |
| `MCP_HOST` / `MCP_PORT` | Non | Écoute SSE (défaut `127.0.0.1:8000`) |
| `MCP_AUTH_TOKEN` | **Oui en SSE** | Bearer requis pour les clients distants ; le serveur refuse de démarrer en SSE sans ce token |
| `MCP_READONLY` | Non | `true`/`1`/`yes` : n'expose que les outils `readOnlyHint: true` |

\* Requis uniquement si pas de dossiers.json.

## Durcissement sécurité (v2.x)

- `api._validate_endpoint()` : appelé en tête de `api_get/post/put/delete` et
  de `DossierManager.parallel_get`. Rejette tout endpoint absolu
  (`scheme://`), protocole-relatif (`//host`), contenant CRLF/antislash, ou
  ne commençant pas par `/`. Empêche la fuite du header `Authorization:
  Bearer <token>` vers un hôte tiers, y compris via `pennylane_multi_dossier_query`.
- `dossier_manager.resolve_secret()` : résout une valeur `${VAR}` depuis
  `os.environ` au moment de construire le client httpx (`_build_client`). Le
  token stocké dans `dossiers.json` peut donc être un placeholder ; le secret
  réel ne vit qu'en mémoire/environnement.
- `DossierManager.load_config()` avertit sur stderr si `dossiers.json` est
  lisible par d'autres utilisateurs (`mode & 0o077`).
- `server._check_sse_auth()` : comparaison du Bearer SSE via
  `hmac.compare_digest` (anti timing-attack). `MCP_AUTH_TOKEN` est
  obligatoire en SSE (sinon `sys.exit(1)`).
- Mode `MCP_READONLY` : wrapper de `mcp.tool` dans `server.py` qui ignore
  l'enregistrement de tout outil dont `annotations["readOnlyHint"]` n'est pas
  strictement `True`.
- Tests : `tests/test_security.py` couvre ces quatre points.

<p align="center">
  <h1 align="center">🧾 Pennylane MCP Server</h1>
  <p align="center">
    Serveur MCP (Model Context Protocol) complet pour l'API comptable <strong>Pennylane V2</strong>
    <br />
    Connectez la comptabilité de <strong>votre société</strong> à un assistant IA
    <br /><br />
    <a href="#installation">Installation</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#fonctionnalités">Fonctionnalités</a> •
    <a href="#utilisation">Utilisation</a>
  </p>
</p>

---

## Présentation

**Pennylane MCP Server** expose l'API Pennylane V2 sous forme de **81 outils MCP** utilisables par n'importe quel LLM compatible (Claude, GPT, Mistral, etc.).

Il permet d'automatiser les opérations comptables quotidiennes d'une société via un assistant IA : consultation du plan comptable, saisie d'écritures, lettrage, balance générale, gestion des factures, devis, et bien plus.

> **Mono-société** : ce serveur pilote **un seul dossier Pennylane**, configuré via un unique token (`PENNYLANE_API_TOKEN`).

### Pourquoi ce projet ?

Beaucoup d'opérations dans Pennylane sont répétitives. Ce serveur MCP permet de :

- **Gagner du temps** en automatisant la saisie, la consultation et le lettrage via le langage naturel
- **Fiabiliser les opérations** grâce à une validation stricte des données (Pydantic v2)

### Qu'est-ce que MCP ?

Le [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) est un protocole ouvert qui permet aux modèles de langage (LLM) d'interagir avec des outils et des sources de données externes de manière standardisée. Ce serveur implémente le protocole MCP pour exposer les fonctionnalités de Pennylane à n'importe quel client LLM compatible.

---

## Prérequis

- **Python** >= 3.11
- **pip** (gestionnaire de paquets Python)
- Un **token API Pennylane** (Company Token)

### Obtenir un token API Pennylane

1. Connectez-vous à [Pennylane](https://app.pennylane.com)
2. Allez dans **Paramètres > Connectivité > Développeurs**
3. Générez un **Company API Token** avec les scopes nécessaires :
   - `ledger_accounts:all` — Comptes
   - `journals:all` — Journaux
   - `ledger_entries:all` — Écritures
   - `trial_balance:readonly` — Balance
   - `fiscal_years:readonly` — Exercices
   - `customers:all` — Clients
   - `supplier_invoices:all` — Factures fournisseurs
   - `customer_invoices:all` — Factures clients

> 💡 Pour un usage en **consultation seule**, générez le token avec uniquement les scopes `:readonly`.

---

## Installation

```bash
# 1. Clonez le dépôt
git clone https://github.com/melvynx/pennylane-mcp-server.git
cd pennylane-mcp-server

# 2. (Recommandé) Créez un environnement virtuel
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# 3. Installez le paquet
pip install -e .
```

---

## Configuration

Configurez votre token Pennylane via une variable d'environnement :

```bash
export PENNYLANE_API_TOKEN="votre_token_pennylane"
```

Ou copiez le fichier `.env.example` :

```bash
cp .env.example .env
# Éditez .env et renseignez votre token
```

### Variables d'environnement

| Variable | Requis | Description |
|----------|--------|-------------|
| `PENNYLANE_API_TOKEN` | **Oui** | Token Bearer Company API Pennylane |
| `MCP_TRANSPORT` | Non | `stdio` (défaut, local) ou `sse` (distant) |
| `MCP_HOST` / `MCP_PORT` | Non | Hôte/port d'écoute en mode SSE (défaut `127.0.0.1:8000`) |
| `MCP_AUTH_TOKEN` | En SSE | Token d'authentification, **obligatoire** en mode SSE |

---

## Intégration avec Claude Desktop

Ajoutez dans votre fichier de configuration Claude Desktop (`claude_desktop_config.json`) :

```json
{
  "mcpServers": {
    "pennylane": {
      "command": "pennylane-mcp-server",
      "env": {
        "PENNYLANE_API_TOKEN": "votre_token_pennylane"
      }
    }
  }
}
```

> **Où trouver ce fichier ?**
> - macOS : `~/Library/Application Support/Claude/claude_desktop_config.json`
> - Windows : `%APPDATA%\Claude\claude_desktop_config.json`

---

## Utilisation

### Lancement direct

```bash
# Avec le token en variable d'environnement
PENNYLANE_API_TOKEN=votre_token pennylane-mcp-server

# Via Python directement
PENNYLANE_API_TOKEN=votre_token python -m pennylane_mcp.server
```

### Exemples de requêtes via LLM

Une fois le serveur connecté à votre LLM, vous pouvez interagir en langage naturel :

**Plan comptable :**
> « Montre-moi tous les comptes clients (411) »

**Écriture comptable :**
> « Passe une écriture de vente : 1 200 EUR TTC (1 000 HT + 200 TVA) pour le client DUPONT »

**Balance générale :**
> « Donne-moi la balance générale du 1er janvier au 31 mars 2025 »

**Lettrage :**
> « Lettre le règlement de 1 200 EUR avec la facture correspondante sur le compte 411001 »

**Factures clients :**
> « Crée une facture pour le client Dupont : prestation de conseil, 2 000 EUR HT, TVA 20% »

**Devis :**
> « Crée un devis pour le client Martin pour une mission d'audit à 5 000 EUR HT »

---

## Fonctionnalités

### Plan comptable

| Outil | Description |
|-------|-------------|
| `pennylane_list_accounts` | Rechercher/lister les comptes (préfixes : 411=clients, 401=fournisseurs, 512=banque) |
| `pennylane_get_account` | Détail d'un compte |
| `pennylane_create_account` | Créer un compte (auto-création client/fournisseur si 411/401) |
| `pennylane_update_account` | Modifier libellé ou lettrage |

### Journaux comptables

| Outil | Description |
|-------|-------------|
| `pennylane_list_journals` | Lister les journaux (ventes, achats, banque, OD, paie) |
| `pennylane_get_journal` | Détail d'un journal |
| `pennylane_create_journal` | Créer un journal (codes : VE, HA, BQ, OD, PA, RB) |

### Écritures comptables

| Outil | Description |
|-------|-------------|
| `pennylane_list_entries` | Lister les écritures (filtres journal, période) |
| `pennylane_get_entry` | Détail complet d'une écriture avec ses lignes |
| `pennylane_create_entry` | Passer une écriture équilibrée (débit = crédit) |
| `pennylane_update_entry` | Modifier une écriture (en-tête + lignes) |
| `pennylane_list_entry_lines` | Lignes d'une écriture spécifique |

### Lignes d'écriture et lettrage

| Outil | Description |
|-------|-------------|
| `pennylane_list_all_entry_lines` | Rechercher des lignes (par compte, journal, période) |
| `pennylane_get_entry_line` | Détail d'une ligne |
| `pennylane_letter_lines` | Lettrer (rapprocher factures et règlements) |
| `pennylane_unletter_lines` | Délettrer |
| `pennylane_link_categories` | Ventilation analytique (catégories avec poids) |
| `pennylane_list_line_categories` | Catégories analytiques d'une ligne |
| `pennylane_list_lettered_lines` | Lignes rapprochées ensemble |

### Clients et fournisseurs

| Outil | Description |
|-------|-------------|
| `pennylane_list_customers` | Lister les clients |
| `pennylane_get_customer` | Détail d'un client |
| `pennylane_create_company_customer` | Créer un client entreprise |
| `pennylane_create_individual_customer` | Créer un client particulier |
| `pennylane_list_suppliers` | Lister les fournisseurs |
| `pennylane_get_supplier` | Détail d'un fournisseur |
| `pennylane_create_supplier` | Créer un fournisseur |

### Factures

| Outil | Description |
|-------|-------------|
| `pennylane_list_customer_invoices` | Lister les factures clients |
| `pennylane_get_customer_invoice` | Détail d'une facture client |
| `pennylane_create_customer_invoice` | Créer une facture client |
| `pennylane_finalize_customer_invoice` | Finaliser un brouillon |
| `pennylane_list_supplier_invoices` | Lister les factures fournisseurs |
| `pennylane_get_supplier_invoice` | Détail d'une facture fournisseur |

### Devis et abonnements

| Outil | Description |
|-------|-------------|
| `pennylane_list_quotes` | Lister les devis |
| `pennylane_get_quote` | Détail d'un devis |
| `pennylane_create_quote` | Créer un devis |
| `pennylane_list_billing_subscriptions` | Lister les abonnements |

### Balance, exercices et exports

| Outil | Description |
|-------|-------------|
| `pennylane_get_trial_balance` | Balance générale par période |
| `pennylane_list_fiscal_years` | Exercices fiscaux et leur statut |
| `pennylane_create_fec_export` | Exporter le FEC (Fichier des Écritures Comptables) |
| `pennylane_create_agl_export` | Exporter le Grand Livre Analytique |

### Suivi des modifications (Changelogs)

| Outil | Description |
|-------|-------------|
| `pennylane_changelog_customers` | Historique des modifications clients |
| `pennylane_changelog_suppliers` | Historique des modifications fournisseurs |
| `pennylane_changelog_products` | Historique des modifications produits |
| `pennylane_changelog_customer_invoices` | Historique des modifications factures clients |
| `pennylane_changelog_supplier_invoices` | Historique des modifications factures fournisseurs |
| `pennylane_changelog_quotes` | Historique des modifications devis |
| `pennylane_changelog_entry_lines` | Historique des modifications lignes d'écriture |
| `pennylane_changelog_transactions` | Historique des modifications transactions bancaires |

### Utilitaires

| Outil | Description |
|-------|-------------|
| `pennylane_whoami` | Vérifier la connexion et les informations société |

---

## Architecture

```
pennylane-mcp-server/
├── pyproject.toml              # Métadonnées et dépendances
├── README.md
├── CLAUDE_CONTEXT.md           # Contexte métier pour le LLM
├── .env.example                # Template de configuration
├── LICENSE                     # Licence MIT
│
└── src/pennylane_mcp/          # Code source
    ├── server.py               # Point d'entrée FastMCP
    ├── constants.py            # URLs, limites, constantes
    ├── models.py               # Modèles Pydantic (validation stricte)
    ├── api.py                  # Client httpx async + validation des endpoints
    ├── utils.py                # Formatage, pagination, troncature
    │
    └── tools/                  # Outils MCP répartis par domaine
        ├── me.py               # Connexion
        ├── accounts.py         # Plan comptable
        ├── journals.py         # Journaux
        ├── entries.py          # Écritures
        ├── entry_lines.py      # Lignes + lettrage + analytique
        ├── trial_balance.py    # Balance + exercices
        ├── customers.py        # Clients
        ├── suppliers.py        # Fournisseurs
        ├── customer_invoices.py # Factures clients
        ├── supplier_invoices.py # Factures fournisseurs
        ├── quotes.py           # Devis
        ├── products.py         # Produits / services
        ├── billing_subscriptions.py # Abonnements
        ├── categories.py       # Catégories analytiques
        ├── exports.py          # Exports FEC / AGL
        └── changelogs.py       # Journaux de modifications
```

---

## Stack technique

| Technologie | Rôle |
|-------------|------|
| [FastMCP](https://github.com/modelcontextprotocol/python-sdk) | Framework MCP Python officiel |
| [httpx](https://www.python-httpx.org/) | Client HTTP asynchrone |
| [Pydantic v2](https://docs.pydantic.dev/) | Validation stricte des entrées |

---

## Comment contribuer

Les contributions sont les bienvenues ! Voici comment étendre le serveur :

1. Créez un modèle Pydantic dans `models.py` pour valider les entrées
2. Créez ou enrichissez un fichier dans `tools/`
3. Décorez votre fonction avec `@mcp.tool(name=..., annotations=...)`
4. Enregistrez le module via `register(mcp)` dans `server.py`

```bash
# Installez en mode développement
pip install -e .

# Testez avec l'inspecteur MCP
mcp dev src/pennylane_mcp/server.py
```

---

## Sécurité

- Le token API n'est **jamais** inclus dans le code source (variable d'environnement uniquement)
- Le fichier `.env` est exclu du dépôt Git via `.gitignore`
- La seule destination réseau est l'API Pennylane : les endpoints sont validés (`api._validate_endpoint`) pour empêcher toute fuite du token vers un hôte tiers (URL absolue / protocole-relatif rejetés)
- En mode SSE, un token d'authentification (`MCP_AUTH_TOKEN`) est **obligatoire** (comparaison à temps constant)
- Toutes les entrées utilisateur sont validées par Pydantic v2 (`extra="forbid"`)

---

## Licence

Ce projet est sous licence [MIT](LICENSE).

---

## Auteur

Développé par **Melvyn Morice** — Expert-comptable mémorialiste passionné par l'IA et l'automatisation.

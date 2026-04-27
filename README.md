# Demo ADIRA — Couche Semantique & IA

Application de demo montrant comment une couche semantique (ontologie + metriques + regles metier) ameliore la generation de requetes SQL par un LLM.

Un utilisateur pose une question metier en langage naturel, Claude (Anthropic) la traduit en SQL Trino, l'execute contre un data warehouse Iceberg, et affiche les resultats avec des visualisations.

## Contexte

L'app utilise les donnees d'une PME B2B fictive (15 commerciaux, 7 regions, 250 clients) et repond a la question centrale **"Pourquoi Lyon a rate son Q3 ?"** a trois niveaux de profondeur :

| Profondeur | Donnees disponibles | Type de reponse |
|---|---|---|
| 1 | Schema ERP brut (noms cryptiques) | Constat chiffre : "CA -23% vs objectif" |
| 2 | + Couche semantique (definitions, regles metier) | Constat fiable : "CA -23%, churn segment PME" |
| 3 | + Donnees non-structurees extraites (appels, tickets) | Diagnostic : "Concurrent Acme cite dans 67% des appels Lyon" |

## Architecture

```
app/
  main.py          API FastAPI : routes /query, /query/no-semantic, /query/cross, /extract, /documents
  llm.py           Interactions Claude (Anthropic SDK) : prompts systeme, parsing JSON
  ontology.py      Chargement ontology.yaml + semantic.yaml, contexte LLM
  database.py      Connexion Trino (HTTPS), execution SQL sur schemas gold/raw
  models.py        Modeles Pydantic (request/response)

data/
  ontology.yaml    Types d'entites, relations, questions suggerees
  semantic.yaml    Metriques (formules SQL), dimensions, patterns de requetes, regles metier
  parquet/         Donnees synthetiques (gold: 10 tables FR / raw: 8 tables ERP)
  documents/       JSON transcriptions d'appels (TR-*) et tickets (TK-*)
  static/          Frontend vanilla JS (Chat, Pipeline extraction, Catalogue, Ontologie)

scripts/
  generate_data.py   Generation des donnees synthetiques (Parquet + JSON)
  load_to_trino.py   Chargement des Parquet dans Trino via INSERT
```

## Prerequis

- Python 3.11+
- Un acces a un cluster Trino avec le catalogue `iceberg` (par defaut : `trino.thelio.app:443`)
- Une cle API Anthropic

## Installation

```bash
git clone https://github.com/Thomas-Lienard/demo-adira.git
cd demo-adira

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Creer un fichier `.env` a la racine :

```env
ANTHROPIC_API_KEY=sk-ant-...
# Optionnel
ANTHROPIC_MODEL=claude-sonnet-4-20250514
TRINO_HOST=trino.thelio.app
TRINO_PORT=443
TRINO_USER=prenom.nom
```

## Chargement des donnees

Generer les donnees synthetiques (Parquet + JSON) :

```bash
python scripts/generate_data.py
```

Charger dans Trino (necessite un cluster Trino accessible) :

```bash
# Schemas gold + raw
python scripts/load_to_trino.py

# Gold uniquement
python scripts/load_to_trino.py --gold

# Raw uniquement
python scripts/load_to_trino.py --raw

# Supprimer et recreer les tables
python scripts/load_to_trino.py --drop
```

## Lancement

```bash
python run.py
```

L'application demarre sur http://localhost:5000 et ouvre le navigateur automatiquement.

## Utilisation

L'interface comporte quatre onglets :

- **Chat** — Poser une question en francais. Trois modes :
  - *Standard* (`/query`) : utilise la couche semantique + schema gold
  - *Comparaison* : execute la meme question avec et sans couche semantique, cote a cote
  - *Analyse croisee* (`/query/cross`) : interroge plusieurs sources (ventes + appels + tickets) puis synthetise
- **Pipeline d'extraction** — Visualise l'extraction de champs structures depuis un document brut (appel ou ticket)
- **Catalogue Semantique** — Parcourir les metriques, dimensions et regles metier definis dans `semantic.yaml`
- **Ontologie** — Graphe interactif des entites et relations (Cytoscape.js)

## API

| Methode | Route | Description |
|---|---|---|
| `POST` | `/query` | Question avec couche semantique (SSE) |
| `POST` | `/query/no-semantic` | Question sans couche semantique (SSE) |
| `POST` | `/query/cross` | Analyse multi-sources (SSE) |
| `POST` | `/extract` | Extraction de champs depuis un document |
| `GET` | `/documents` | Liste des documents disponibles |
| `GET` | `/documents/{id}` | Contenu d'un document |
| `GET` | `/semantic` | Catalogue semantique complet |

Les routes `/query*` utilisent le Server-Sent Events (SSE) : elles emettent des evenements `step` (progression) puis un evenement `result` (reponse finale).

Corps des requetes POST `/query*` :

```json
{ "question": "Quel est le CA par region au Q3 2025 ?" }
```

## Stack technique

- **Backend** : FastAPI + Uvicorn
- **LLM** : Claude (Anthropic SDK)
- **Data warehouse** : Trino + Iceberg
- **Frontend** : HTML/CSS/JS vanilla, Chart.js, Cytoscape.js
- **Donnees** : Parquet (genere avec Pandas/PyArrow)

## Dialecte SQL

Le SQL genere est du **Trino SQL** (pas PostgreSQL/MySQL). Exemples de syntaxe specifique :

```sql
-- Literals date
WHERE date_commande >= DATE '2025-07-01'

-- Fonctions
QUARTER(date_commande)
DATE_DIFF('day', date1, date2)
DATE_FORMAT(date, '%Y-%m')
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Demo ADIRA is a live demo app built for an ADIRA presentation (April 24, 2026, ~70 attendees, 50/50 technical/non-technical). Presenters: Thomas Lienard (Thelio, data consultant) + Nicolas Balligand (CDDO, GL events). Talk title: "L'IA pour la Data et la Data pour l'IA".

The app showcases how an ontology/semantic layer improves LLM-generated SQL queries, using a fictional French B2B SME (15 commerciaux, 7 regions, 250 clients). It uses Claude (Anthropic API) to translate natural-language business questions into Trino SQL, execute them against an Iceberg data warehouse, and visualize results.

The app is entirely in French (UI, data, prompts, column names).

## Demo Narrative

The demo is built around one question asked three times at increasing depth:

**The golden question: "Pourquoi Lyon a rate son Q3 ?"**

| Depth | Setup | Answer type | Expected output |
|-------|-------|-------------|-----------------|
| 1 | Raw ERP schema only (cryptic column names), LLM guesses | Le combien | "CA -23% vs objectif Q3." |
| 2 | + Semantic layer (governed definitions, business rules) | Le combien, avec fiabilite | "CA -23%, churn sur le segment PME." |
| 3 | + Unstructured data extracted to tables (calls, tickets) | Le pourquoi | "Concurrent Acme cite sur 67% des appels Lyon." |

The point: each added layer moves the answer from constat to diagnosis.

**Key conceptual distinction (punchline of the talk):** "Un RAG trouve un document. Un pipeline d'extraction cree une statistique." This is NOT a RAG chatbot — it is an extraction pipeline that writes governed, aggregatable, versionable structured rows.

**Pipeline reference scenario:** A call between "Marie Dubois" (commercial) and "M. Lefevre" (Lefevre SAS) where the client mentions Acme offering -18% pricing. The extraction must produce a 15-column row including `concurrent_cite: "Acme"`, `sentiment: negatif`, `probabilite_churn: 0.72`, `montant_risque_eur: 145000`.

**Audience calibration:** Visual before/after comparisons and concrete numbers for non-technical half; real tool names (Trino, Iceberg, LLM-as-extraction-pipeline) for technical half.

## Commands

```bash
# Setup
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt

# Run the app (starts FastAPI on http://localhost:5000 with auto-reload)
python run.py

# Generate synthetic data (Parquet files + JSON documents)
python scripts/generate_data.py

# Load Parquet data into Trino
python scripts/load_to_trino.py [--gold] [--raw] [--drop]
```

## Architecture

**FastAPI backend** (`app/`) serving a single-page frontend (`data/static/`):

- `app/main.py` — API routes: `/query` (with semantic layer), `/query/no-semantic` (raw schema), `/query/cross` (multi-source diagnostic), `/extract` (document field extraction), `/documents` (list/get JSON documents)
- `app/llm.py` — All Claude API interactions. Builds system prompts from ontology+semantic context, sends questions to Claude, parses JSON responses. Uses `anthropic` SDK with model from `ANTHROPIC_MODEL` env var (default: claude-sonnet-4-20250514)
- `app/ontology.py` — Loads `data/ontology.yaml` and `data/semantic.yaml`, builds the graph data for the UI and the text context injected into LLM prompts
- `app/database.py` — Trino connection (HTTPS to `trino.thelio.app:443`, catalog `iceberg`). Two schemas: `demo_adira_gold` (clean French names) and `demo_adira_raw` (cryptic ERP-style names)
- `app/models.py` — Pydantic request/response models

**Data layer** (`data/`):

- `data/ontology.yaml` — Entity types (Region, Commercial, Client, Commande, etc.), relationships, and suggested questions
- `data/semantic.yaml` — Metrics with SQL formulas, dimensions with GROUP BY clauses, query patterns (comparaison/evolution/classement/diagnostic/valeur_unique), business rules, and table aliases
- `data/parquet/` — Synthetic data in two schemas: `demo_adira_gold/` (10 tables with French column names) and `demo_adira_raw/` (8 tables with abbreviated ERP names)
- `data/documents/` — JSON files for transcriptions (`TR-*.json`) and tickets (`TK-*.json`), each with `raw_text` and `extracted_fields`

**Frontend** (`data/static/`): Vanilla JS single-page app with four tabs — Chat (natural language queries with Chart.js visualizations), Pipeline d'extraction (before/after document extraction), Catalogue Semantique (metrics/dimensions/rules browser), Ontologie (Cytoscape.js interactive graph).

**Scripts** (`scripts/`):

- `generate_data.py` — Generates all synthetic Parquet + JSON data with deterministic seed (42). The AURA region Q3 2025 data is intentionally degraded to create an interesting diagnostic scenario
- `load_to_trino.py` — Reads Parquet files and inserts rows into Trino via SQL INSERT with retry logic

## Key Design Decisions

- The semantic layer (`ontology.yaml` + `semantic.yaml`) is the core differentiator: it provides the LLM with entity definitions, SQL formulas, table aliases, business rules, and query patterns so it generates correct, governed SQL. Framing: it's a "translator for the LLM", not an ontology
- The "comparison mode" runs the same question through both `/query` (with semantic layer, gold schema) and `/query/no-semantic` (raw schema only) side-by-side — this is the Depth 1 vs Depth 2 moment in the demo
- The "cross analysis" mode (`/query/cross`) generates multiple SQL queries targeting different data sources (structured + extracted calls + extracted tickets) then synthesizes results — this is the Depth 3 moment
- The AURA region Q3 2025 data is intentionally degraded in `generate_data.py` (lower order probabilities, more negative sentiment, more competitor mentions for Acme Corp) to create the "Lyon rate son Q3" scenario
- All LLM responses must be valid JSON (no markdown backticks); `_parse_json_response` in `llm.py` handles cleanup
- The two Trino schemas exist specifically to contrast raw ERP (`demo_adira_raw`: `tbl_ord_hdr.ord_dt`, `tbl_cst_acct.cst_nm`) vs governed gold (`demo_adira_gold`: `date_commande`, `nom_client`)

## Environment

- Requires `ANTHROPIC_API_KEY` in `.env`
- Trino connection defaults: host `trino.thelio.app`, port 443, HTTPS, user `thomas.lienard`
- SQL dialect is Trino (not PostgreSQL/MySQL) — use DATE literals like `DATE '2025-07-01'`, functions like `QUARTER()`, `DATE_DIFF()`, `DATE_FORMAT()`

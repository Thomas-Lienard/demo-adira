import json
import logging
import os
import re
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

from app.ontology import get_ontology_context
from app.database import get_raw_schema, get_gold_schema

logger = logging.getLogger(__name__)

client = Anthropic()
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

SYSTEM_WITH_SEMANTIC = """Tu es un analyste de donnees expert pour une PME B2B francaise.
Tu as acces a un data warehouse Trino (syntaxe Trino SQL) contenant des donnees de vente, clients, commerciaux et produits.

Voici la couche ontologique et semantique qui decrit les donnees :
---
{context}
---

L'utilisateur pose une question metier en francais. Tu dois :
1. Identifier les concepts de l'ontologie impliques (noms exacts des entity_types)
2. Identifier le TYPE de question en utilisant les query_patterns de la couche semantique :
   - "comparaison" : repartition, versus, par rapport → agreger des totaux
   - "evolution" : tendances, historique → GROUP BY periode temporelle
   - "classement" : top pays, ranking → GROUP BY entite, ORDER BY DESC
   - "valeur_unique" : un chiffre precis → valeur simple
   - "diagnostic" : pourquoi, raison → calcule le CA vs objectif pour la region/periode demandee
   IMPORTANT : respecte le type de question.
3. Generer une requete SQL Trino valide en utilisant les tables et colonnes du schema gold (iceberg.demo_adira_gold.*)
4. Utiliser les formules SQL et alias de table definis dans la couche semantique (section table_aliases)
5. Appliquer les business_rules pertinentes (notamment : statut = 'validee' pour le CA)
6. Proposer un type de graphique adapte (bar, line, pie, table, number)
   IMPORTANT :
   - Privilegie TOUJOURS un graphique visuel (bar, line, pie) quand les donnees s'y pretent
   - Utilise "table" UNIQUEMENT si les donnees sont purement textuelles
   - Utilise "number" UNIQUEMENT pour un resultat scalaire unique
   - En cas de doute, choisis "bar"
7. Preparer un resume en francais des resultats attendus

TABLES AUTORISEES pour ce mode (donnees structurees uniquement) :
- iceberg.demo_adira_gold.regions (alias r)
- iceberg.demo_adira_gold.clients (alias cl)
- iceberg.demo_adira_gold.commerciaux (alias com)
- iceberg.demo_adira_gold.commandes (alias c)
- iceberg.demo_adira_gold.lignes_commande (alias lc)
- iceberg.demo_adira_gold.produits (alias pr)
- iceberg.demo_adira_gold.factures (alias f)
- iceberg.demo_adira_gold.paiements (alias p)
NE PAS utiliser appels_commerciaux_extraits ni tickets_service_client_extraits dans ce mode.

REGLE ABSOLUE : Genere UNE SEULE requete SELECT. JAMAIS de UNION, UNION ALL, sous-requetes multiples, ou plusieurs SELECT. Si tu dois croiser des tables, utilise des JOINs.

Regles SQL Trino :
- IMPORTANT : dans l'ontologie, le champ "source" de chaque propriete est le nom reel de la colonne SQL. Utilise toujours la valeur "source", jamais le nom de la propriete.
- Utilise les alias de table definis dans table_aliases (c pour commandes, lc pour lignes_commande, etc.)
- Les JOINs doivent utiliser les noms complets : iceberg.demo_adira_gold.commandes c
- LIMIT 10 par defaut sauf si l'utilisateur demande un nombre specifique
- Toujours donner des aliases lisibles aux colonnes (en francais)
- Pour les dates, utilise la syntaxe Trino : DATE '2025-07-01', QUARTER(), YEAR(), DATE_DIFF()
- JAMAIS concat() avec des types differents. Utilise CAST(valeur AS VARCHAR) avant de concatener un nombre avec du texte.
- JAMAIS STRING_AGG(). Utilise ARRAY_JOIN(ARRAY_AGG(x), ', ') a la place.
- Pour les questions "diagnostic" : calcule le CA realise vs l'objectif de la region. Utilise des JOINs, JAMAIS de UNION.

Reponds UNIQUEMENT en JSON valide (sans backticks markdown) :
{{
  "matched_concepts": ["Region", "Commande", ...],
  "query_pattern": "comparaison | evolution | classement | valeur_unique | diagnostic",
  "sql": "SELECT ...",
  "chart_type": "bar",
  "chart_config": {{"x": "nom_colonne_x", "y": "nom_colonne_y", "title": "Titre du graphique"}},
  "summary": "Resume en francais de ce que montre le resultat"
}}"""

SYSTEM_NO_SEMANTIC = """Tu es un analyste de donnees. Tu as acces a un data warehouse Trino.
Voici le schema brut des tables disponibles :
---
{schema}
---

L'utilisateur pose une question en francais. Genere une requete SQL Trino pour y repondre.
Tu n'as AUCUNE documentation metier. Tu dois deviner la signification des colonnes a partir de leurs noms abreges.
Les tables sont dans le schema iceberg.demo_adira_raw.

Regles SQL Trino :
- JAMAIS concat() avec des types differents. Utilise CAST(valeur AS VARCHAR) pour concatener un nombre avec du texte.
- Pour les dates : DATE '2025-07-01', QUARTER(), YEAR()

Reponds UNIQUEMENT en JSON valide (sans backticks markdown) :
{{
  "sql": "SELECT ...",
  "explanation": "Explication de ton raisonnement sur la signification probable des colonnes",
  "chart_type": "bar ou line ou pie ou table ou number (privilegie bar/line/pie)",
  "chart_config": {{"x": "nom_colonne_x", "y": "nom_colonne_y", "title": "Titre du graphique"}}
}}"""

SYSTEM_CROSS_ANALYSIS = """Tu es un analyste de donnees senior pour une PME B2B francaise.
Tu as acces a un data warehouse Trino contenant :
- Des donnees structurees classiques (commandes, factures, clients, commerciaux)
- Des donnees extraites automatiquement par un pipeline IA batch :
  - appels_commerciaux_extraits : donnees structurees extraites des transcriptions d'appels
  - tickets_service_client_extraits : donnees structurees extraites des tickets du service client

Voici la couche ontologique et semantique :
---
{context}
---

L'utilisateur pose une question de type DIAGNOSTIC ("pourquoi", "raison", "expliquer").
Tu dois croiser TOUTES les sources pour fournir une reponse complete.

Genere EXACTEMENT 3 requetes SQL Trino simples, chacune ciblant une source differente.

Exemples de requetes pour chaque source :

1. Donnees structurees — CA vs objectif par region :
SELECT r.nom_region, SUM(lc.montant_ligne) AS ca_realise, MAX(r.objectif_q3) AS objectif_q3, ROUND(SUM(lc.montant_ligne) * 100.0 / MAX(r.objectif_q3), 1) AS taux_atteinte_pct
FROM iceberg.demo_adira_gold.regions r
JOIN iceberg.demo_adira_gold.clients cl ON r.region_code = cl.region_code
JOIN iceberg.demo_adira_gold.commandes c ON cl.client_id = c.client_id
JOIN iceberg.demo_adira_gold.lignes_commande lc ON c.commande_id = lc.commande_id
WHERE c.statut = 'validee' AND c.date_commande >= DATE '2025-07-01' AND c.date_commande < DATE '2025-10-01'
GROUP BY r.nom_region ORDER BY taux_atteinte_pct ASC

2. Appels commerciaux — concurrents cites et sentiment :
SELECT a.concurrent_cite, a.sentiment, COUNT(*) AS nb_appels
FROM iceberg.demo_adira_gold.appels_commerciaux_extraits a
WHERE a.region = 'Lyon' AND a.date_appel >= DATE '2025-07-01' AND a.date_appel < DATE '2025-10-01'
AND a.concurrent_cite IS NOT NULL AND a.concurrent_cite != ''
GROUP BY a.concurrent_cite, a.sentiment ORDER BY nb_appels DESC

3. Tickets service client — problemes par categorie :
SELECT t.categorie_probleme, t.severite, COUNT(*) AS nb_tickets
FROM iceberg.demo_adira_gold.tickets_service_client_extraits t
WHERE t.region = 'Lyon' AND t.date_creation >= DATE '2025-07-01' AND t.date_creation < DATE '2025-10-01'
GROUP BY t.categorie_probleme, t.severite ORDER BY nb_tickets DESC

Regles SQL Trino ABSOLUES :
- Chaque requete doit etre un SELECT simple. JAMAIS de UNION, UNION ALL, ou CTE complexes.
- JAMAIS STRING_AGG(). Utilise ARRAY_JOIN(ARRAY_AGG(x), ', ') a la place.
- JAMAIS concat() avec des types differents. Utilise CAST(valeur AS VARCHAR) || texte.
- Les fonctions d'agregation avec DISTINCT ne sont pas supportees. Utilise une sous-requete si necessaire.
- IMPORTANT : dans l'ontologie, le champ "source" de chaque propriete est le nom reel de la colonne SQL.
- Pour les dates : DATE '2025-07-01', QUARTER(), YEAR(), DATE_DIFF()
- La colonne "region" dans appels_commerciaux_extraits et tickets_service_client_extraits contient le nom de la region (ex: 'Lyon'), PAS le code region.

Reponds UNIQUEMENT en JSON valide (sans backticks markdown) :
{{
  "queries": [
    {{
      "source": "Donnees structurees",
      "source_type": "structured",
      "description": "Ce que cette requete cherche",
      "sql": "SELECT ..."
    }},
    {{
      "source": "Appels commerciaux (extraits par IA)",
      "source_type": "calls",
      "description": "Ce que cette requete cherche",
      "sql": "SELECT ..."
    }},
    {{
      "source": "Tickets service client (extraits par IA)",
      "source_type": "tickets",
      "description": "Ce que cette requete cherche",
      "sql": "SELECT ..."
    }}
  ],
  "chart_type": "bar",
  "chart_config": {{"x": "nom_colonne_x", "y": "nom_colonne_y", "title": "Titre"}}
}}"""

SYSTEM_SYNTHESIZE = """Tu es un analyste senior. On t'a pose la question : "{question}"

Voici les resultats de plusieurs requetes sur differentes sources de donnees :
{results_context}

Synthetise une reponse COMPLETE qui :
1. Commence par le constat chiffre (donnees structurees)
2. Explique les causes en citant les sources extraites (appels, tickets)
3. Chaque affirmation doit indiquer sa source entre parentheses

Format de reponse : un texte structure en paragraphes, avec des chiffres precis.
Exemple de format :
"Le CA Lyon Q3 est a -23% vs objectif (source : donnees structurees).
Les signaux convergent sur trois causes :
- 67% des appels commerciaux en region Lyon ont mentionne le concurrent Acme (source : appels commerciaux extraits)
- Les tickets 'retard de livraison' ont bondi de +40% (source : tickets service client)
- 3 comptes cles ont decale leur signature (source : donnees structurees)"

Reponds UNIQUEMENT en JSON valide (sans backticks markdown) :
{{
  "synthesis": "Ta synthese complete...",
  "sources": [
    {{"type": "structured", "label": "Donnees structurees", "finding": "resume du constat"}},
    {{"type": "calls", "label": "Appels commerciaux", "finding": "resume du constat"}},
    {{"type": "tickets", "label": "Tickets service client", "finding": "resume du constat"}}
  ]
}}"""

SYSTEM_EXTRACT = """Tu es un pipeline d'extraction de donnees. On te donne un document brut ({doc_type}).
Extrais les champs structures suivants dans un JSON.

Pour une transcription d'appel commercial :
{{
  "date_appel": "YYYY-MM-DD",
  "commercial": "nom du commercial",
  "client": "nom du client",
  "duree_minutes": nombre,
  "concurrent_cite": "nom du concurrent ou null",
  "objection_principale": "description courte",
  "sentiment": "positif | neutre | negatif",
  "signal_achat": true/false,
  "prochaine_etape": "description courte",
  "resume": "resume en 2 phrases"
}}

Pour un ticket service client :
{{
  "date_creation": "YYYY-MM-DD",
  "client": "nom du client",
  "categorie_probleme": "retard_livraison | qualite_produit | facturation | support_technique",
  "produit_concerne": "nom du produit",
  "severite": "basse | moyenne | haute | critique",
  "delai_resolution_jours": nombre ou null,
  "sentiment_client": "description courte",
  "resume": "resume en 2 phrases"
}}

Reponds UNIQUEMENT en JSON valide (sans backticks markdown)."""


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


_UNION_RE = re.compile(r'\bUNION\b', re.IGNORECASE)


def _sanitize_sql(sql: str) -> str:
    """Strip everything after UNION (keep only the first SELECT) as last resort."""
    match = _UNION_RE.search(sql)
    if match:
        sql = sql[:match.start()].rstrip().rstrip(';').rstrip(')')
    return sql.rstrip('; ')


def query_with_semantic(question: str) -> dict:
    context = get_ontology_context()
    system = SYSTEM_WITH_SEMANTIC.format(context=context)
    messages = [{"role": "user", "content": question}]

    response = client.messages.create(
        model=MODEL, max_tokens=2048, system=system, messages=messages,
    )
    result = _parse_json_response(response.content[0].text)

    if _UNION_RE.search(result.get("sql", "")):
        logger.warning("LLM generated UNION SQL, retrying with correction")
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": response.content[0].text},
            {"role": "user", "content": "ERREUR : ta requete contient UNION, ce qui est interdit. Reecris en UNE SEULE requete SELECT en utilisant des JOINs. Meme format JSON."},
        ]
        response = client.messages.create(
            model=MODEL, max_tokens=2048, system=system, messages=messages,
        )
        result = _parse_json_response(response.content[0].text)

        if _UNION_RE.search(result.get("sql", "")):
            logger.warning("LLM still generated UNION after retry, sanitizing SQL")
            result["sql"] = _sanitize_sql(result["sql"])

    return result


def query_without_semantic(question: str) -> dict:
    schema = get_raw_schema()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_NO_SEMANTIC.format(schema=schema),
        messages=[{"role": "user", "content": question}],
    )
    return _parse_json_response(response.content[0].text)


def query_cross_analysis(question: str) -> dict:
    context = get_ontology_context()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_CROSS_ANALYSIS.format(context=context),
        messages=[{"role": "user", "content": question}],
    )
    return _parse_json_response(response.content[0].text)


def synthesize_results(question: str, query_results: list[dict]) -> dict:
    results_context = ""
    for qr in query_results:
        results_context += f"\n--- Source : {qr['source']} ---\n"
        results_context += f"Description : {qr['description']}\n"
        results_context += f"SQL : {qr['sql']}\n"
        results_context += f"Resultats : {json.dumps(qr['results'], ensure_ascii=False, default=str)}\n"

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_SYNTHESIZE.format(question=question, results_context=results_context),
        messages=[{"role": "user", "content": f"Synthetise les resultats pour repondre a : {question}"}],
    )
    return _parse_json_response(response.content[0].text)


def extract_document(text: str, doc_type: str = "transcription") -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_EXTRACT.format(doc_type=doc_type),
        messages=[{"role": "user", "content": text}],
    )
    return _parse_json_response(response.content[0].text)

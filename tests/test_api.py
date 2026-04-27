from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

QUESTION = "Pourquoi Lyon a rate son Q3 ?"

MOCK_SEMANTIC_RESULT = {
    "matched_concepts": ["Region", "Commande"],
    "query_pattern": "diagnostic",
    "sql": "SELECT r.nom_region, SUM(lc.quantite * lc.prix_unitaire) AS ca FROM iceberg.demo_adira_gold.commandes c JOIN iceberg.demo_adira_gold.lignes_commande lc ON c.id_commande = lc.id_commande JOIN iceberg.demo_adira_gold.regions r ON c.id_region = r.id_region WHERE c.statut = 'validee' AND QUARTER(c.date_commande) = 3 GROUP BY r.nom_region",
    "chart_type": "bar",
    "chart_config": {"x": "nom_region", "y": "ca", "title": "CA par region Q3"},
    "summary": "Le CA de la region AURA est en baisse de 23% par rapport a l'objectif Q3.",
}

MOCK_NO_SEMANTIC_RESULT = {
    "sql": "SELECT h.rgn_cd, SUM(d.qty * d.unit_prc) AS total FROM iceberg.demo_adira_raw.tbl_ord_hdr h JOIN iceberg.demo_adira_raw.tbl_ord_dtl d ON h.ord_id = d.ord_id GROUP BY h.rgn_cd",
    "explanation": "J'ai suppose que tbl_ord_hdr contient les commandes et rgn_cd represente le code region.",
    "chart_type": "bar",
    "chart_config": {"x": "rgn_cd", "y": "total", "title": "Total par region"},
}

MOCK_CROSS_RESULT = {
    "queries": [
        {
            "source": "Donnees structurees",
            "source_type": "structured",
            "description": "CA par region Q3",
            "sql": "SELECT r.nom_region, SUM(lc.quantite * lc.prix_unitaire) AS ca FROM iceberg.demo_adira_gold.commandes c JOIN iceberg.demo_adira_gold.lignes_commande lc ON c.id_commande = lc.id_commande JOIN iceberg.demo_adira_gold.regions r ON c.id_region = r.id_region WHERE c.statut = 'validee' GROUP BY r.nom_region",
        },
        {
            "source": "Appels commerciaux (extraits par IA)",
            "source_type": "calls",
            "description": "Concurrents cites dans les appels Lyon",
            "sql": "SELECT concurrent_cite, COUNT(*) AS nb FROM iceberg.demo_adira_gold.appels_commerciaux_extraits WHERE region = 'AURA' GROUP BY concurrent_cite ORDER BY nb DESC",
        },
        {
            "source": "Tickets service client (extraits par IA)",
            "source_type": "tickets",
            "description": "Categories de problemes Lyon",
            "sql": "SELECT categorie_probleme, COUNT(*) AS nb FROM iceberg.demo_adira_gold.tickets_service_client_extraits WHERE region = 'AURA' GROUP BY categorie_probleme",
        },
    ],
    "chart_type": "bar",
    "chart_config": {"x": "nom_region", "y": "ca", "title": "Diagnostic Lyon Q3"},
}

MOCK_SYNTHESIS = {
    "synthesis": "Le CA Lyon Q3 est a -23% vs objectif. 67% des appels mentionnent Acme.",
    "sources": [
        {"type": "structured", "label": "Donnees structurees", "finding": "CA -23%"},
        {"type": "calls", "label": "Appels commerciaux", "finding": "Acme cite 67%"},
        {"type": "tickets", "label": "Tickets service client", "finding": "Retard livraison +40%"},
    ],
}

MOCK_GOLD_ROWS = [
    {"nom_region": "AURA", "ca": 450000},
    {"nom_region": "IDF", "ca": 820000},
]

MOCK_RAW_ROWS = [
    {"rgn_cd": "AURA", "total": 450000},
    {"rgn_cd": "IDF", "total": 820000},
]


class TestQueryNoSemantic:
    """UC1: Raw ERP schema, no semantic layer."""

    @patch("app.main.execute_query_raw", return_value=MOCK_RAW_ROWS)
    @patch("app.main.query_without_semantic", return_value=MOCK_NO_SEMANTIC_RESULT)
    def test_response_structure(self, mock_llm, mock_db):
        res = client.post("/query/no-semantic", json={"question": QUESTION})
        assert res.status_code == 200
        data = res.json()
        assert data["question"] == QUESTION
        assert "sql" in data
        assert "explanation" in data
        assert "results" in data
        assert "chart_type" in data
        assert "matched_concepts" not in data

    @patch("app.main.execute_query_raw", return_value=MOCK_RAW_ROWS)
    @patch("app.main.query_without_semantic", return_value=MOCK_NO_SEMANTIC_RESULT)
    def test_uses_raw_schema(self, mock_llm, mock_db):
        res = client.post("/query/no-semantic", json={"question": QUESTION})
        data = res.json()
        assert "demo_adira_raw" in data["sql"]
        assert "tbl_" in data["sql"]
        mock_llm.assert_called_once_with(QUESTION)
        mock_db.assert_called_once()

    @patch("app.main.execute_query_raw", return_value=MOCK_RAW_ROWS)
    @patch("app.main.query_without_semantic", return_value=MOCK_NO_SEMANTIC_RESULT)
    def test_returns_explanation(self, mock_llm, mock_db):
        res = client.post("/query/no-semantic", json={"question": QUESTION})
        data = res.json()
        assert len(data["explanation"]) > 0
        assert data["results"] == MOCK_RAW_ROWS


class TestQueryWithSemantic:
    """UC2: Gold schema with semantic layer."""

    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_with_semantic", return_value=MOCK_SEMANTIC_RESULT)
    def test_response_structure(self, mock_llm, mock_db):
        res = client.post("/query", json={"question": QUESTION})
        assert res.status_code == 200
        data = res.json()
        assert data["question"] == QUESTION
        assert "sql" in data
        assert "summary" in data
        assert "matched_concepts" in data
        assert "chart_type" in data
        assert "chart_config" in data
        assert "results" in data

    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_with_semantic", return_value=MOCK_SEMANTIC_RESULT)
    def test_uses_gold_schema(self, mock_llm, mock_db):
        res = client.post("/query", json={"question": QUESTION})
        data = res.json()
        assert "demo_adira_gold" in data["sql"]
        assert "statut = 'validee'" in data["sql"]

    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_with_semantic", return_value=MOCK_SEMANTIC_RESULT)
    def test_has_matched_concepts(self, mock_llm, mock_db):
        res = client.post("/query", json={"question": QUESTION})
        data = res.json()
        assert len(data["matched_concepts"]) > 0
        assert "Region" in data["matched_concepts"]
        assert "Commande" in data["matched_concepts"]

    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_with_semantic", return_value=MOCK_SEMANTIC_RESULT)
    def test_returns_results_and_summary(self, mock_llm, mock_db):
        res = client.post("/query", json={"question": QUESTION})
        data = res.json()
        assert data["results"] == MOCK_GOLD_ROWS
        assert len(data["summary"]) > 0


class TestQueryCrossAnalysis:
    """UC3: Cross analysis with structured + unstructured data."""

    @patch("app.main.synthesize_results", return_value=MOCK_SYNTHESIS)
    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_cross_analysis", return_value=MOCK_CROSS_RESULT)
    def test_response_structure(self, mock_cross, mock_db, mock_synth):
        res = client.post("/query/cross", json={"question": QUESTION})
        assert res.status_code == 200
        data = res.json()
        assert data["question"] == QUESTION
        assert "synthesis" in data
        assert "queries" in data
        assert "sources" in data
        assert isinstance(data["queries"], list)
        assert isinstance(data["sources"], list)

    @patch("app.main.synthesize_results", return_value=MOCK_SYNTHESIS)
    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_cross_analysis", return_value=MOCK_CROSS_RESULT)
    def test_has_three_source_types(self, mock_cross, mock_db, mock_synth):
        res = client.post("/query/cross", json={"question": QUESTION})
        data = res.json()
        assert len(data["queries"]) == 3
        source_types = {q["source_type"] for q in data["queries"]}
        assert source_types == {"structured", "calls", "tickets"}

    @patch("app.main.synthesize_results", return_value=MOCK_SYNTHESIS)
    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_cross_analysis", return_value=MOCK_CROSS_RESULT)
    def test_each_query_has_required_fields(self, mock_cross, mock_db, mock_synth):
        res = client.post("/query/cross", json={"question": QUESTION})
        data = res.json()
        for q in data["queries"]:
            assert "source" in q
            assert "source_type" in q
            assert "description" in q
            assert "sql" in q
            assert "results" in q

    @patch("app.main.synthesize_results", return_value=MOCK_SYNTHESIS)
    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_cross_analysis", return_value=MOCK_CROSS_RESULT)
    def test_calls_synthesize_after_queries(self, mock_cross, mock_db, mock_synth):
        client.post("/query/cross", json={"question": QUESTION})
        mock_synth.assert_called_once()
        args = mock_synth.call_args
        assert args[0][0] == QUESTION
        assert len(args[0][1]) == 3

    @patch("app.main.synthesize_results", return_value=MOCK_SYNTHESIS)
    @patch("app.main.execute_query_gold", return_value=MOCK_GOLD_ROWS)
    @patch("app.main.query_cross_analysis", return_value=MOCK_CROSS_RESULT)
    def test_synthesis_content(self, mock_cross, mock_db, mock_synth):
        res = client.post("/query/cross", json={"question": QUESTION})
        data = res.json()
        assert len(data["synthesis"]) > 0
        assert len(data["sources"]) == 3
        source_types = {s["type"] for s in data["sources"]}
        assert source_types == {"structured", "calls", "tickets"}

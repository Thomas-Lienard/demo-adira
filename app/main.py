import json
import logging
import os
import traceback
from pathlib import Path
from typing import Generator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.models import (
    QueryRequest, QueryResponse, NoSemanticResponse,
    CrossAnalysisResponse, ExtractRequest, ExtractResponse,
)
from app.ontology import load_semantic, get_ontology_context
from app.database import execute_query_gold, execute_query_raw, get_raw_schema
from app.llm import (
    query_with_semantic, query_without_semantic,
    query_cross_analysis, synthesize_results, extract_document,
)


def _sse_event(event: str, data: dict | str) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"

STATIC_DIR = str(Path(__file__).resolve().parent.parent / "data" / "static")
DOCS_DIR = str(Path(__file__).resolve().parent.parent / "data" / "documents")

app = FastAPI(title="Demo ADIRA - Couche Semantique & IA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/style.css")
async def style():
    return FileResponse(os.path.join(STATIC_DIR, "style.css"), media_type="text/css")


@app.get("/app.js")
async def js():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"), media_type="application/javascript")


@app.get("/semantic")
async def semantic():
    return load_semantic()


@app.post("/query")
def query(req: QueryRequest):
    def generate() -> Generator[str, None, None]:
        try:
            yield _sse_event("step", {"message": "Chargement du contexte..."})
            get_ontology_context()

            yield _sse_event("step", {"message": "Generation de la requete..."})
            llm_result = query_with_semantic(req.question)
            sql = llm_result["sql"]

            yield _sse_event("step", {"message": "Execution de la requete..."})
            try:
                results = execute_query_gold(sql)
            except Exception as e:
                logger.error("SQL execution error: %s", e)
                results = []
                llm_result["summary"] = f"Erreur SQL : {e}"

            yield _sse_event("step", {"message": "Mise en forme..."})
            payload = QueryResponse(
                question=req.question,
                sql=sql,
                results=results,
                summary=llm_result.get("summary", ""),
                matched_concepts=llm_result.get("matched_concepts", []),
                chart_type=llm_result.get("chart_type", "table"),
                chart_config=llm_result.get("chart_config", {}),
            )
            yield _sse_event("result", payload.model_dump())
        except BaseException as e:
            logger.error("Error in /query: %s", traceback.format_exc())
            payload = QueryResponse(
                question=req.question, sql="", results=[],
                summary=f"Erreur : {e}", matched_concepts=[],
                chart_type="table", chart_config={},
            )
            yield _sse_event("result", payload.model_dump())

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/query/no-semantic")
def query_no_semantic(req: QueryRequest):
    def generate() -> Generator[str, None, None]:
        try:
            yield _sse_event("step", {"message": "Lecture du schema..."})
            get_raw_schema()

            yield _sse_event("step", {"message": "Generation de la requete..."})
            llm_result = query_without_semantic(req.question)
            sql = llm_result.get("sql")

            yield _sse_event("step", {"message": "Execution de la requete..."})
            try:
                results = execute_query_raw(sql) if sql else None
                error = None
            except Exception as e:
                results = None
                error = str(e)

            yield _sse_event("step", {"message": "Mise en forme..."})
            payload = NoSemanticResponse(
                question=req.question,
                sql=sql,
                results=results,
                error=error,
                explanation=llm_result.get("explanation", ""),
                chart_type=llm_result.get("chart_type", "table"),
                chart_config=llm_result.get("chart_config", {}),
            )
            yield _sse_event("result", payload.model_dump())
        except BaseException as e:
            logger.error("Error in /query/no-semantic: %s", traceback.format_exc())
            payload = NoSemanticResponse(
                question=req.question, sql=None, results=None,
                error=str(e), explanation="",
            )
            yield _sse_event("result", payload.model_dump())

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/query/cross")
def query_cross(req: QueryRequest):
    def generate() -> Generator[str, None, None]:
        try:
            yield _sse_event("step", {"message": "Chargement du contexte..."})
            get_ontology_context()

            yield _sse_event("step", {"message": "Analyse multi-sources..."})
            llm_result = query_cross_analysis(req.question)

            queries = llm_result.get("queries", [])
            query_results = []
            all_results = []
            for i, q in enumerate(queries, 1):
                yield _sse_event("step", {"message": f"Requete {i}/{len(queries)} : {q['source']}..."})
                try:
                    rows = execute_query_gold(q["sql"])
                except Exception as e:
                    logger.error("Cross-query SQL error: %s", e)
                    rows = [{"erreur": str(e)}]

                query_results.append({
                    "source": q["source"],
                    "source_type": q.get("source_type", "structured"),
                    "description": q["description"],
                    "sql": q["sql"],
                    "results": rows,
                })
                if rows and "erreur" not in rows[0]:
                    all_results.extend(rows)

            yield _sse_event("step", {"message": "Synthese des resultats..."})
            synthesis = synthesize_results(req.question, query_results)

            yield _sse_event("step", {"message": "Mise en forme..."})
            payload = CrossAnalysisResponse(
                question=req.question,
                synthesis=synthesis.get("synthesis", ""),
                queries=query_results,
                sources=synthesis.get("sources", []),
                chart_type=llm_result.get("chart_type", "bar"),
                chart_config=llm_result.get("chart_config", {}),
                results=all_results[:20],
            )
            yield _sse_event("result", payload.model_dump())
        except BaseException as e:
            logger.error("Error in /query/cross: %s", traceback.format_exc())
            payload = CrossAnalysisResponse(
                question=req.question,
                synthesis=f"Erreur : {e}",
                queries=[], sources=[], results=[],
            )
            yield _sse_event("result", payload.model_dump())

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/extract")
def extract(req: ExtractRequest):
    try:
        fields = extract_document(req.document_text, req.document_type)
        return ExtractResponse(extracted_fields=fields, raw_text=req.document_text[:500])
    except Exception as e:
        logger.error("Error in /extract: %s", traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.get("/documents")
def list_documents():
    docs = []
    for doc_type in ["transcriptions", "tickets"]:
        type_dir = os.path.join(DOCS_DIR, doc_type)
        if not os.path.exists(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(type_dir, fname), "r", encoding="utf-8") as f:
                doc = json.load(f)
            docs.append({
                "id": doc["id"],
                "type": doc["type"],
                "metadata": doc.get("metadata", {}),
            })
    return docs


@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    for doc_type in ["transcriptions", "tickets"]:
        type_dir = os.path.join(DOCS_DIR, doc_type)
        if not os.path.exists(type_dir):
            continue
        for fname in os.listdir(type_dir):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(type_dir, fname), "r", encoding="utf-8") as f:
                doc = json.load(f)
            if doc["id"] == doc_id:
                return doc
    return JSONResponse(status_code=404, content={"detail": "Document not found"})

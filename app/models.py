from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    sql: str
    results: list[dict]
    summary: str
    matched_concepts: list[str]
    chart_type: str
    chart_config: dict


class NoSemanticResponse(BaseModel):
    question: str
    sql: str | None = None
    results: list[dict] | None = None
    error: str | None = None
    explanation: str = ""
    chart_type: str = "table"
    chart_config: dict = {}


class CrossAnalysisResponse(BaseModel):
    question: str
    synthesis: str
    queries: list[dict] = []
    sources: list[dict] = []
    chart_type: str = "table"
    chart_config: dict = {}
    results: list[dict] = []


class ExtractRequest(BaseModel):
    document_text: str
    document_type: str = "transcription"


class ExtractResponse(BaseModel):
    extracted_fields: dict
    raw_text: str

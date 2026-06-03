"""Pydantic request/response schemas for FVSC Core Service."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CreateSpaceRequest(BaseModel):
    name: str
    dim: int = 64


class SpaceMeta(BaseModel):
    name: str
    dim: int
    concept_count: int
    chunk_count: int
    ingest_count: int
    ingests_since_save: int
    last_modified: Optional[float] = None


class IngestRequest(BaseModel):
    text: str
    source_id: str
    format: Literal["plain", "md"] = "plain"


class IngestResponse(BaseModel):
    chunks_added: int
    concepts_total: int
    source_id: str


class DeepenRequest(BaseModel):
    iterations: int = 3
    alpha: float = 0.7


class FacetInfo(BaseModel):
    weight: float
    strength: float


class ConceptReport(BaseModel):
    term: str
    found: bool
    component_count: int = 0
    mass: float = 0.0
    polysemy: float = 0.0
    purity: float = 0.0
    facets: List[FacetInfo] = []
    contains: List[Dict] = []         # {term, weight}
    contained_in: List[Dict] = []     # {term, weight}


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5


class ChunkHit(BaseModel):
    chunk_id: str
    source_id: str
    text: str
    score: float
    matched_concepts: List[str]


class RetrieveResponse(BaseModel):
    hits: List[ChunkHit]


class CompareResponse(BaseModel):
    shared_concepts: List[dict]
    divergent: List[dict]
    aligned: List[dict]
    global_similarity: float


class ErrorResponse(BaseModel):
    detail: str

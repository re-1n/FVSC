"""Pydantic request/response schemas for FVSC Core Service."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CreateSpaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    dim: int = Field(default=64, ge=8, le=1024)


class SpaceMeta(BaseModel):
    name: str
    dim: int
    concept_count: int
    chunk_count: int
    ingest_count: int
    ingests_since_save: int
    last_modified: Optional[float] = None


class IngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000_000)
    source_id: str = Field(min_length=1, max_length=1024)
    format: Literal["plain", "md"] = "plain"


class IngestResponse(BaseModel):
    chunks_added: int
    concepts_total: int
    source_id: str


class DeepenRequest(BaseModel):
    iterations: int = Field(default=3, ge=1, le=20)
    alpha: float = Field(default=0.7, ge=0.0, le=1.0)


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
    facets: List[FacetInfo] = Field(default_factory=list)
    contains: List[Dict] = Field(default_factory=list)         # {term, weight}
    contained_in: List[Dict] = Field(default_factory=list)     # {term, weight}


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=100)


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

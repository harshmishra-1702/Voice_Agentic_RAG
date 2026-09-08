"""
RAG module — ChromaDB-backed semantic search over SRE runbook chunks.

Uses local sentence-transformers (all-MiniLM-L6-v2) for embeddings —
zero API cost, runs entirely on-device.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logger = logging.getLogger("voiceops.rag")

COLLECTION_NAME = "memorylab_knowledge"
CHROMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # ~80MB, fast, good for small corpora


@dataclass
class SearchResult:
    """A single RAG search result with source attribution."""

    text: str
    source_title: str
    concept: str
    evidence_level: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_title": self.source_title,
            "concept": self.concept,
            "evidence_level": self.evidence_level,
            "score": round(self.score, 4),
        }


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    """Create the local sentence-transformer embedding function.

    Model is downloaded on first use (~80MB) and cached locally.
    No API key needed.
    """
    return SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )


_collection_cache = None


def get_collection() -> chromadb.Collection:
    """Get or create the ChromaDB collection with persistent storage."""
    global _collection_cache
    if _collection_cache is not None:
        return _collection_cache
        
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    _collection_cache = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )
    return _collection_cache


async def search_knowledge(query: str, top_k: int = 3) -> list[SearchResult]:
    """Semantic search over the knowledge corpus.

    Returns the top-k most relevant chunks with source file attribution.
    ChromaDB's query is synchronous, so we run it in a thread executor
    to avoid blocking the event loop (critical for interruption timing).
    """
    # ChromaDB's query is synchronous. We run it directly to avoid PyTorch OpenMP thread deadlocks on Windows.
    collection = get_collection()

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    search_results: list[SearchResult] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        search_results.append(
            SearchResult(
                text=doc,
                source_title=meta.get("source_title", "Unknown"),
                concept=meta.get("concept", "unknown"),
                evidence_level=meta.get("evidence_level", "unknown"),
                score=1.0 - dist,  # cosine distance → similarity
            )
        )

    logger.info(
        "RAG search for '%s': %d results (top score: %.3f)",
        query[:60],
        len(search_results),
        search_results[0].score if search_results else 0.0,
    )
    return search_results

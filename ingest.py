"""
Runbook Ingestion Script — chunks markdown files and embeds them into ChromaDB.

Usage:
    python ingest.py

Reads all .md files from the runbooks/ directory, splits them into ~300-word
chunks with 50-word overlap, and upserts into the 'sre_runbooks' ChromaDB
collection using local sentence-transformers (all-MiniLM-L6-v2).

No API key needed — embeddings run entirely on-device.
"""

from __future__ import annotations

import os
import sys

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "runbooks")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "sre_runbooks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking parameters
CHUNK_SIZE_WORDS = 300
OVERLAP_WORDS = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks: list[str] = []

    if len(words) <= chunk_size:
        return [text.strip()] if text.strip() else []

    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap

    return chunks


def load_runbooks() -> list[tuple[str, str, str]]:
    """Load all markdown files and chunk them.

    Returns list of (chunk_id, chunk_text, source_filename).
    """
    all_chunks: list[tuple[str, str, str]] = []
    chunk_counter = 0

    if not os.path.isdir(RUNBOOKS_DIR):
        print(f"Error: runbooks directory not found at {RUNBOOKS_DIR}")
        sys.exit(1)

    md_files = sorted(f for f in os.listdir(RUNBOOKS_DIR) if f.endswith(".md"))

    if not md_files:
        print(f"Error: no .md files found in {RUNBOOKS_DIR}")
        sys.exit(1)

    for filename in md_files:
        filepath = os.path.join(RUNBOOKS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = chunk_text(content)
        for chunk in chunks:
            chunk_id = f"{filename}::chunk-{chunk_counter}"
            all_chunks.append((chunk_id, chunk, filename))
            chunk_counter += 1

        print(f"  {filename}: {len(chunks)} chunk(s)")

    return all_chunks


def ingest() -> None:
    """Main ingestion pipeline."""
    print(f"\n{'='*50}")
    print("VoiceOps — Runbook Ingestion")
    print(f"{'='*50}\n")

    # Load and chunk
    print(f"Loading runbooks from: {RUNBOOKS_DIR}")
    chunks = load_runbooks()
    print(f"\nTotal chunks: {len(chunks)}")

    # Initialize ChromaDB with local embeddings
    print(f"\nInitializing ChromaDB at: {CHROMA_PATH}")
    print(f"Embedding model: {EMBEDDING_MODEL} (local, no API key needed)")
    print("(First run will download the model — ~80MB)")

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )

    # Delete existing collection if present (clean re-ingest)
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # Upsert chunks
    ids = [c[0] for c in chunks]
    documents = [c[1] for c in chunks]
    metadatas = [{"source": c[2]} for c in chunks]

    print(f"\nEmbedding and upserting {len(chunks)} chunks...")
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"\nIngestion complete!")
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  Chunks ingested: {collection.count()}")
    print(f"  Persisted to: {CHROMA_PATH}")

    # Quick verification search
    print(f"\n{'='*50}")
    print("Verification search: 'switch failure recovery'")
    print(f"{'='*50}")
    results = collection.query(
        query_texts=["switch failure outage recovery steps"],
        n_results=2,
    )
    for i, (doc, meta) in enumerate(
        zip(results["documents"][0], results["metadatas"][0])  # type: ignore[index]
    ):
        print(f"\n  Result {i+1} (source: {meta['source']}):")
        print(f"  {doc[:150]}...")

    print(f"\n{'='*50}")
    print("Done! Run the agent with: python -m agent.main dev")
    print(f"{'='*50}")


if __name__ == "__main__":
    ingest()

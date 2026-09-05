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

# Force HuggingFace offline to completely eliminate the 30-40s network latency
os.environ["HF_HUB_OFFLINE"] = "1"

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


def load_runbooks(target_filename: str = None) -> list[tuple[str, str, str]]:
    """Load files and chunk them. Supports .md, .txt, .pdf."""
    all_chunks: list[tuple[str, str, str]] = []
    chunk_counter = 0

    if not os.path.isdir(RUNBOOKS_DIR):
        print(f"Error: directory not found at {RUNBOOKS_DIR}")
        sys.exit(1)

    if target_filename:
        files = [target_filename]
    else:
        valid_exts = (".md", ".txt", ".pdf")
        files = sorted(f for f in os.listdir(RUNBOOKS_DIR) if f.lower().endswith(valid_exts))

    if not files:
        print(f"Error: no valid files (.md, .txt, .pdf) found in {RUNBOOKS_DIR}")
        sys.exit(1)

    for filename in files:
        filepath = os.path.join(RUNBOOKS_DIR, filename)
        content = ""
        
        try:
            if filename.lower().endswith(".pdf"):
                import pypdf
                reader = pypdf.PdfReader(filepath)
                text_pages = [page.extract_text() for page in reader.pages if page.extract_text()]
                content = "\n".join(text_pages)
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

        if not content.strip():
            print(f"  {filename}: empty or unreadable")
            continue

        chunks = chunk_text(content)
        for chunk in chunks:
            chunk_id = f"{filename}::chunk-{chunk_counter}"
            all_chunks.append((chunk_id, chunk, filename))
            chunk_counter += 1

        print(f"  {filename}: {len(chunks)} chunk(s)")

    if not all_chunks:
        print("Error: No content could be extracted from files.")
        sys.exit(1)

    return all_chunks


_cached_client = None
_cached_embedding_fn = None

def get_collection():
    global _cached_client, _cached_embedding_fn
    if _cached_client is None:
        _cached_client = chromadb.PersistentClient(path=CHROMA_PATH)
    if _cached_embedding_fn is None:
        _cached_embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return _cached_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_cached_embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

def ingest(target_filename: str = None) -> None:
    """Main ingestion pipeline."""
    print(f"\n{'='*50}")
    print("VoiceOps — Runbook Ingestion")
    print(f"{'='*50}\n")

    # Load and chunk
    print(f"Loading runbooks from: {RUNBOOKS_DIR}")
    chunks = load_runbooks(target_filename)
    print(f"\nTotal chunks: {len(chunks)}")

    # Initialize ChromaDB with local embeddings
    print(f"\nInitializing ChromaDB at: {CHROMA_PATH}")
    collection = get_collection()

    # Upsert chunks
    ids = [c[0] for c in chunks]
    documents = [c[1] for c in chunks]
    metadatas = [{"source": c[2]} for c in chunks]

    print(f"\nEmbedding and upserting {len(chunks)} chunks...")
    collection.upsert(
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
    target = sys.argv[1] if len(sys.argv) > 1 else None
    ingest(target)

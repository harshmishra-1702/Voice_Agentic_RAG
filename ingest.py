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

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
COLLECTION_NAME = "memorylab_knowledge"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking parameters
CHUNK_SIZE_WORDS = 300
OVERLAP_WORDS = 50

def load_knowledge() -> list[dict]:
    import json
    import glob
    
    all_chunks = []
    chunk_counter = 0

    if not os.path.isdir(KNOWLEDGE_DIR):
        print(f"Error: directory not found at {KNOWLEDGE_DIR}")
        return all_chunks

    json_files = glob.glob(os.path.join(KNOWLEDGE_DIR, "**", "*.json"), recursive=True)
    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    chunk_id = f"{item['document_id']}::chunk-{chunk_counter}"
                    item['chunk_id'] = chunk_id
                    
                    # Store original text for chunking or just use the text as a whole chunk
                    text = item.get("text", "")
                    if text:
                        all_chunks.append({
                            "id": chunk_id,
                            "text": text,
                            "metadata": {
                                "source_title": item.get("source_title", "Unknown"),
                                "concept": item.get("concept", "unknown"),
                                "evidence_level": item.get("evidence_level", "unknown"),
                                "system": item.get("system", "Unknown"),
                            }
                        })
                        chunk_counter += 1
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

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
    print("MemoryLab — Knowledge Ingestion")
    print(f"{'='*50}\n")

    chunks = []
    if target_filename:
        print(f"Loading single file: {target_filename}")
        runbooks_dir = os.path.join(os.path.dirname(__file__), "runbooks")
        filepath = os.path.join(runbooks_dir, target_filename)
        if os.path.exists(filepath):
            content = ""
            ext = os.path.splitext(target_filename)[1].lower()
            try:
                if ext == ".pdf":
                    import pypdf
                    with open(filepath, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        for page in reader.pages:
                            content += page.extract_text() + "\n"
                elif ext in [".md", ".txt"]:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                else:
                    # Fallback for docx/pptx or other files if libraries aren't installed
                    # We'll try to read it as text, ignoring errors
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
            except Exception as e:
                print(f"Failed to read file {target_filename}: {e}")
                
            # Simple chunking for dynamic text/md files
            words = content.split()
            chunk_size = 300
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk_text = " ".join(chunk_words)
                chunks.append({
                    "id": f"{target_filename}::chunk-{i}",
                    "text": chunk_text,
                    "metadata": {
                        "source_title": target_filename,
                        "concept": "Dynamic Upload",
                        "evidence_level": "dynamic"
                    }
                })
        else:
            print(f"File not found: {filepath}")
    else:
        # Load and chunk original JSON corpus
        print(f"Loading knowledge from: {KNOWLEDGE_DIR}")
        chunks = load_knowledge()

    print(f"\nTotal chunks to process: {len(chunks)}")

    if not chunks:
        print("No chunks to ingest.")
        return

    # Initialize ChromaDB with local embeddings
    print(f"\nInitializing ChromaDB at: {CHROMA_PATH}")
    collection = get_collection()

    # Upsert chunks
    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

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
    print("Verification search: 'recurrent memory'")
    print(f"{'='*50}")
    results = collection.query(
        query_texts=["recurrent memory"],
        n_results=2,
    )
    if results and results.get("documents") and results["documents"][0]:
        for i, (doc, meta) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])  # type: ignore[index]
        ):
            print(f"\n  Result {i+1} (source: {meta['source_title']}):")
            print(f"  {doc[:150]}...")

    print(f"\n{'='*50}")
    print("Done! Run the agent with: python -m agent.main dev")
    print(f"{'='*50}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    ingest(target)

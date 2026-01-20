import re
import spacy
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import requests
from typing import List, Dict
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_loader import settings

# ==========================================================
# CONFIG
# ==========================================================

# --- Elasticsearch ---
es = Elasticsearch(settings.ELASTICSEARCH_URL)

# --- Qdrant ---
qdrant = QdrantClient(url=settings.QDRANT_URL)

# --- Embeddings (Ollama) ---
session = requests.Session()

# --- Lemmatizer (French) ---
print("Loading spaCy French model...")
_nlp = spacy.load(settings.SPACY_MODEL)

# Hybrid weights
BM25_WEIGHT = settings.BM25_WEIGHT
VECTOR_WEIGHT = settings.VECTOR_WEIGHT

TOP_K = settings.RETRIEVER_TOP_K
FINAL_K = settings.RETRIEVER_FINAL_K


# ==========================================================
# NORMALIZATION + LEMMATIZATION
# ==========================================================

def normalize_and_lemmatize(text: str) -> str:
    """Clean markdown + lowercase + French lemmatization."""
    # --- Remove markdown blocks ---
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"#+\s*", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"[*_]{1,3}", " ", text)
    text = re.sub(r"^\s*[-*+]\s*", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s*", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\|.*\|", " ", text)
    text = re.sub(r"[-*_]{3,}", " ", text)
    text = re.sub(r"[{}\[\]]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip().lower()

    # Lemmatize
    doc = _nlp(text)
    lemmas = [t.lemma_ for t in doc if not t.is_punct and not t.is_space]

    return " ".join(lemmas)


# ==========================================================
# EMBEDDING (Qdrant)
# ==========================================================

def _embed(text: str):
    resp = session.post(
        f"{settings.OLLAMA_BASE_URL}/api/embeddings",
        json={"model": settings.EMBED_MODEL, "prompt": text}
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


# ==========================================================
# BM25 SEARCH
# ==========================================================

def bm25_search(query: str, top_k=TOP_K):
    query_lem = normalize_and_lemmatize(query)

    resp = es.search(
        index=settings.ELASTICSEARCH_INDEX,
        size=top_k,
        query={"match": {"text": query_lem}},
        stored_fields=["doc_id"]
    )

    results = []
    for hit in resp["hits"]["hits"]:
        results.append({
            "id": hit["fields"]["doc_id"][0],
            "score": hit["_score"],
            "method": "bm25"
        })
    return results


# ==========================================================
# QDRANT SEARCH
# ==========================================================

def vector_search(query: str, top_k=TOP_K):
    vec = _embed(query)

    res = qdrant.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vec,
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )

    results = []
    for pt in res.points:
        results.append({
            "id": pt.id,
            "score": pt.score,
            "chunk_text": pt.payload.get("chunk_text", ""),
            "hash": pt.payload.get("hash"),
            "metadata": pt.payload.get("metadata"),
            "method": "vector"
        })
    return results


# ==========================================================
# FETCH CHUNK FROM QDRANT
# ==========================================================

def fetch_chunk(point_id: str):
    res = qdrant.retrieve(
        collection_name=settings.QDRANT_COLLECTION,
        ids=[point_id],
        with_payload=True,
        with_vectors=False
    )
    if not res:
        return None

    pt = res[0]
    return {
        "id": pt.id,
        "chunk_text": pt.payload.get("chunk_text", ""),
        "hash": pt.payload.get("hash"),
        "metadata": pt.payload.get("metadata")
    }


# ==========================================================
# HYBRID RRF FUSION (dynamic top_k)
# ==========================================================

def hybrid_re_rank(bm25_res, vec_res, final_k):
    """
    Combine BM25 + vector results using RRF.
    final_k: number of results to return.
    """

    scores = {}  # {doc_id: {"bm25": float, "vec": float}}

    # --- BM25 scoring ---
    bm25_sorted = sorted(bm25_res, key=lambda x: -x["score"])
    for rank, item in enumerate(bm25_sorted):
        doc_id = item["id"]
        scores.setdefault(doc_id, {"bm25": 0, "vec": 0})
        scores[doc_id]["bm25"] = 1 / (rank + 60)

    # --- Vector scoring ---
    vec_sorted = sorted(vec_res, key=lambda x: -x["score"])
    for rank, item in enumerate(vec_sorted):
        doc_id = item["id"]
        scores.setdefault(doc_id, {"bm25": 0, "vec": 0})
        scores[doc_id]["vec"] = 1 / (rank + 60)

    # --- Weighted merge ---
    fused = []
    for doc_id, s in scores.items():
        fused_score = BM25_WEIGHT * s["bm25"] + VECTOR_WEIGHT * s["vec"]
        fused.append((doc_id, fused_score))

    # --- Sort & return final_k ---
    fused_sorted = sorted(fused, key=lambda x: -x[1])[:final_k]
    return fused_sorted



# ==========================================================
# PUBLIC API — THE ONLY FUNCTION THE USER CALLS
# ==========================================================

def retrieve(prompt: str, top_k: int = 5):
    """
    Full hybrid pipeline:
    - top_k BM25 candidates
    - top_k vector candidates
    - Fuse and return top_k final results
    """
    # 1. BM25
    bm25_results = bm25_search(prompt, top_k)

    # 2. Vector
    vector_results = vector_search(prompt, top_k)

    # 3. Fusion
    fused = hybrid_re_rank(bm25_results, vector_results, final_k=top_k)

    # 4. Fetch chunks from Qdrant
    output = []
    for doc_id, fused_score in fused:
        chunk = fetch_chunk(doc_id)
        if chunk:
            chunk["fused_score"] = fused_score
            output.append(chunk)

    # Sort again by fused score just to be clean
    output = sorted(output, key=lambda x: -x["fused_score"])

    return output

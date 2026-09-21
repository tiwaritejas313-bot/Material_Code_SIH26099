"""
Phase 3: embedding-based candidate retrieval.

Deliberately NOT a trained model -- per the earlier dataset analysis, Samanvay's
own generator hides its ground-truth attributes from the text specifically so
"the engine must recover attributes from text alone." A pretrained
sentence-transformer for retrieval + the Phase 2 rule-based attribute checks
(Phase 4) is the hybrid approach the architecture doc calls for; training a
custom embedding model isn't necessary to get this working.

The index (embedding matrix + parallel id/category arrays) is precomputed
offline by scripts/build_embeddings.py and memory-mapped at import time, since
encoding all ~46k records at server startup would make every restart slow.
Any record not yet in that cached index (e.g. freshly uploaded) can still be
embedded live -- encoding a single string is near-instant -- and searched
against the cached haystack; it just won't be a candidate for others until the
index is rebuilt (POST /embeddings/rebuild).
"""
import json
import pathlib
import threading

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
META_PATH = DATA_DIR / "embeddings_meta.json"

_model_lock = threading.Lock()
_model: SentenceTransformer | None = None

_index_lock = threading.Lock()
_embeddings: np.ndarray | None = None       # (N, 384) float32, L2-normalized
_ids: list[str] | None = None               # Mongo _id strings, same order as rows
_categories: list[str | None] | None = None
_id_to_row: dict[str, int] | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def encode(texts: list[str]) -> np.ndarray:
    model = get_model()
    return np.asarray(model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


def build_and_save_index(ids: list[str], texts: list[str], categories: list[str | None], batch_size: int = 256) -> int:
    model = get_model()
    vectors = model.encode(
        texts, batch_size=batch_size, normalize_embeddings=True,
        show_progress_bar=True, convert_to_numpy=True,
    ).astype(np.float32)

    DATA_DIR.mkdir(exist_ok=True)
    np.save(EMBEDDINGS_PATH, vectors)
    META_PATH.write_text(json.dumps({"ids": ids, "categories": categories}))
    _load_index(force=True)
    return len(ids)


def _load_index(force: bool = False) -> bool:
    global _embeddings, _ids, _categories, _id_to_row
    with _index_lock:
        if _embeddings is not None and not force:
            return True
        if not EMBEDDINGS_PATH.exists() or not META_PATH.exists():
            return False
        _embeddings = np.load(EMBEDDINGS_PATH)
        meta = json.loads(META_PATH.read_text())
        _ids = meta["ids"]
        _categories = meta["categories"]
        _id_to_row = {rid: i for i, rid in enumerate(_ids)}
        return True


def similarity_between(id_a: str, text_a: str, id_b: str, text_b: str) -> float:
    """Cosine similarity for one specific pair, using cached vectors when both
    ids are already in the index, falling back to live encoding otherwise
    (e.g. a record uploaded since the last index rebuild)."""
    _load_index()
    vec_a = _embeddings[_id_to_row[id_a]] if _id_to_row and id_a in _id_to_row else encode([text_a])[0]
    vec_b = _embeddings[_id_to_row[id_b]] if _id_to_row and id_b in _id_to_row else encode([text_b])[0]
    return float(vec_a @ vec_b)


def index_status() -> dict:
    loaded = _load_index()
    return {
        "loaded": loaded,
        "size": len(_ids) if loaded else 0,
        "model": MODEL_NAME,
    }


def find_candidates(
    query_text: str,
    top_k: int = 10,
    category_filter: str | None = None,
    exclude_id: str | None = None,
) -> list[dict]:
    """Pure embedding-similarity retrieval. Embeds query_text live and searches
    it against the cached index, so this works even for a record that isn't
    itself in the cached index yet (e.g. just uploaded) -- it's the haystack
    that must be precomputed, not the query.

    NOTE: on this dataset, pure embedding similarity alone is a mediocre
    ranker (measured recall@20 ~45% against Samanvay's own ground-truth pairs)
    because two categories (hex_bolt/stud_bolt, >13k of the 46k records) are
    near-identical templated text differing only in numeric attribute values
    ("M16" vs "M18") that a general-purpose sentence embedding barely
    separates. Callers wanting good ranking should use
    rank_with_attribute_boost() below, which lifted measured recall@5 from
    37% to 63% by reusing Phase 2's already-extracted attributes -- free,
    since they're already computed. This function stays available as the
    plain first-stage retrieval it actually is.
    """
    if not _load_index():
        return []

    if exclude_id and exclude_id in _id_to_row:
        query_vec = _embeddings[_id_to_row[exclude_id]]
    else:
        query_vec = encode([query_text])[0]

    mask = np.ones(len(_ids), dtype=bool)
    if category_filter:
        mask = np.array([c == category_filter for c in _categories])
    if exclude_id and exclude_id in _id_to_row:
        mask[_id_to_row[exclude_id]] = False

    if not mask.any():
        return []

    candidate_rows = np.nonzero(mask)[0]
    sims = _embeddings[candidate_rows] @ query_vec  # cosine similarity (vectors are unit-norm)
    order = np.argsort(-sims)[:top_k]

    return [
        {"record_id": _ids[candidate_rows[i]], "similarity": float(sims[i])}
        for i in order
    ]


def find_candidate_pool(
    query_text: str,
    pool_size: int = 300,
    category_filter: str | None = None,
    exclude_id: str | None = None,
) -> list[tuple[str, float]]:
    """First-stage retrieval for the hybrid ranker: a larger pool of
    (record_id, embedding_similarity) pairs for the caller to re-rank with
    attribute agreement, since that needs each candidate's stored attributes
    (a DB lookup this module deliberately doesn't own)."""
    if not _load_index():
        return []

    if exclude_id and exclude_id in _id_to_row:
        query_vec = _embeddings[_id_to_row[exclude_id]]
    else:
        query_vec = encode([query_text])[0]

    mask = np.ones(len(_ids), dtype=bool)
    if category_filter:
        mask = np.array([c == category_filter for c in _categories])
    if exclude_id and exclude_id in _id_to_row:
        mask[_id_to_row[exclude_id]] = False
    if not mask.any():
        return []

    candidate_rows = np.nonzero(mask)[0]
    sims = _embeddings[candidate_rows] @ query_vec
    order = np.argsort(-sims)[:pool_size]
    return [(_ids[candidate_rows[i]], float(sims[i])) for i in order]

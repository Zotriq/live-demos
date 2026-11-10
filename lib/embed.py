"""Free local embeddings (bge-small via fastembed, ONNX on CPU); no API key needed."""

from __future__ import annotations

import streamlit as st

MODEL = "BAAI/bge-small-en-v1.5"
DIM = 384


@st.cache_resource(show_spinner="Loading the embedding model…")
def _model():
    try:
        from fastembed import TextEmbedding
        return TextEmbedding(MODEL)
    except Exception:  # download blocked (offline dev): callers fall back to a hashing embedder
        return None


def embed(texts: list[str]) -> list[list[float]]:
    model = _model()
    if model is None:
        import hashlib
        import math
        out = []
        for t in texts:  # deterministic bag-of-words hashing, only for offline development
            v = [0.0] * DIM
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
    return [v.tolist() for v in model.embed(texts)]


class LangChainEmbeddings:
    """The two methods LangChain vector stores call."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return embed([text])[0]

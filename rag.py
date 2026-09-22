"""Minimal RAG: chunk a patient_record.md, embed each chunk, and retrieve the
most relevant chunks for the current conversation turn via cosine similarity.

Deliberately not a vector database — see docs/DECISIONS.md #9. A scenario's
patient record is at most a few dozen paragraphs, so a plain Python list of
embeddings compared with numpy is both simpler and fast enough. Async because
the real embedder (OpenAI's) is an async API call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

import numpy as np

EmbedFn = Callable[[str], Awaitable[np.ndarray]]


def chunk_markdown(text: str) -> list[str]:
    """Split on blank lines into paragraph-level chunks, dropping anything
    that's empty or whitespace-only."""
    raw_chunks = text.split("\n\n")
    return [chunk.strip() for chunk in raw_chunks if chunk.strip()]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


@dataclass
class PatientHistoryIndex:
    chunks: list[str]
    vectors: list[np.ndarray]
    _embed_fn: EmbedFn

    @classmethod
    async def build(cls, chunks: list[str], embed_fn: EmbedFn) -> "PatientHistoryIndex":
        if not chunks:
            raise ValueError("Cannot build a PatientHistoryIndex from zero chunks")
        vectors = [await embed_fn(chunk) for chunk in chunks]
        return cls(chunks=list(chunks), vectors=vectors, _embed_fn=embed_fn)

    async def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        query_vector = await self._embed_fn(query)
        scored = [
            (_cosine_similarity(query_vector, vector), chunk)
            for vector, chunk in zip(self.vectors, self.chunks)
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    @classmethod
    async def from_markdown_file(cls, path, embed_fn: EmbedFn) -> "PatientHistoryIndex":
        text = path.read_text(encoding="utf-8")
        return await cls.build(chunk_markdown(text), embed_fn=embed_fn)

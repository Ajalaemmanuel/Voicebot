import numpy as np
import pytest

from rag import PatientHistoryIndex, chunk_markdown


def test_chunk_markdown_splits_on_blank_lines():
    text = """First paragraph about a visit in 2022.

Second paragraph about an allergy to penicillin.

Third paragraph about a family history of diabetes.
"""
    chunks = chunk_markdown(text)

    assert len(chunks) == 3
    assert "2022" in chunks[0]
    assert "penicillin" in chunks[1]
    assert "diabetes" in chunks[2]


def test_chunk_markdown_drops_empty_and_whitespace_only_chunks():
    text = "Only one real paragraph here.\n\n\n   \n\n"

    chunks = chunk_markdown(text)

    assert chunks == ["Only one real paragraph here."]


def _fake_embed_factory():
    """Deterministic fake async embedder: maps known substrings to
    orthogonal-ish vectors so we can assert exact retrieval ranking without a
    real API call."""
    vectors = {
        "penicillin": np.array([1.0, 0.0, 0.0]),
        "diabetes": np.array([0.0, 1.0, 0.0]),
        "knee": np.array([0.0, 0.0, 1.0]),
    }

    async def embed(text: str) -> np.ndarray:
        for key, vec in vectors.items():
            if key in text:
                return vec
        return np.array([0.3, 0.3, 0.3])

    return embed


async def test_index_retrieves_most_similar_chunk_first():
    embed = _fake_embed_factory()
    chunks = [
        "Patient reported a penicillin allergy in 2019.",
        "Family history includes type 2 diabetes.",
        "Follow-up requested for chronic knee pain.",
    ]
    index = await PatientHistoryIndex.build(chunks, embed_fn=embed)

    results = await index.retrieve("Any concerns about diabetes in the family?", top_k=1)

    assert results == ["Family history includes type 2 diabetes."]


async def test_index_retrieve_top_k_orders_by_similarity_descending():
    embed = _fake_embed_factory()
    chunks = [
        "Patient reported a penicillin allergy in 2019.",
        "Family history includes type 2 diabetes.",
        "Follow-up requested for chronic knee pain.",
    ]
    index = await PatientHistoryIndex.build(chunks, embed_fn=embed)

    results = await index.retrieve("knee pain follow up", top_k=2)

    assert results[0] == "Follow-up requested for chronic knee pain."
    assert len(results) == 2


async def test_index_retrieve_top_k_larger_than_corpus_returns_all():
    embed = _fake_embed_factory()
    chunks = ["Only chunk about penicillin."]
    index = await PatientHistoryIndex.build(chunks, embed_fn=embed)

    results = await index.retrieve("penicillin", top_k=5)

    assert results == ["Only chunk about penicillin."]


async def test_index_build_rejects_empty_chunk_list():
    with pytest.raises(ValueError):
        await PatientHistoryIndex.build([], embed_fn=_fake_embed_factory())

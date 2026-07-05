"""Chunking, pgvector similarity search, and the confidence blend — shared by ingest and query."""

import asyncpg

CHUNK_SIZE_WORDS = 500
CHUNK_OVERLAP_WORDS = 50
TOP_K = 5


def chunk_text(
    text: str, size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS
) -> list[str]:
    """Word-count-based chunking (~500 words, 50 overlap). No empty chunks; stable ordering."""
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks = []
    start = 0
    while start < len(words):
        chunk = " ".join(words[start : start + size])
        chunks.append(chunk)
        start += step
    return chunks


def to_vector_literal(embedding: list[float]) -> str:
    """Render an embedding as a pgvector input literal, e.g. '[0.1,0.2,...]'."""
    return "[" + ",".join(repr(x) for x in embedding) + "]"


def blend_confidence(mean_similarity: float, self_check_score: float) -> float:
    """Confidence = 0.5 * mean retrieval similarity + 0.5 * LLM self-check score (SPEC §3.1)."""
    return 0.5 * mean_similarity + 0.5 * self_check_score


async def top_k_chunks(
    pool: asyncpg.Pool, embedding: list[float], k: int = TOP_K
) -> list[asyncpg.Record]:
    """Top-k chunks by cosine similarity (1 - cosine distance), joined with their document title."""
    return await pool.fetch(
        """
        SELECT
            kb_documents.title AS title,
            kb_chunks.chunk_index AS chunk_index,
            kb_chunks.content AS content,
            1 - (kb_chunks.embedding <=> $1::vector) AS similarity
        FROM kb_chunks
        JOIN kb_documents ON kb_documents.id = kb_chunks.document_id
        ORDER BY kb_chunks.embedding <=> $1::vector
        LIMIT $2
        """,
        to_vector_literal(embedding),
        k,
    )

# ADR-003 — pgvector over an external vector database

**Context.** RAG retrieval needs cosine-similarity search over KB chunk embeddings (10 seed docs,
15 chunks — small scale for this portfolio project). Options were a dedicated vector database
(Pinecone, Weaviate, Qdrant) or an extension on the Postgres instance the project already runs.

**Decision.** Use `pgvector` (via the `pgvector/pgvector:pg16` image) in the same Postgres instance
that holds `tickets`, `messages`, and `llm_calls` — `kb_chunks.embedding vector(1536)` with an HNSW
index (`vector_cosine_ops`), queried with the `<=>` operator.

**Consequences.**
- One database to run, back up, and reason about instead of two — no separate vector-DB service,
  no cross-service consistency concerns between ticket data and embeddings.
- Couples retrieval scale to Postgres/pgvector's own limits — accepted at this project's scale
  (thousands, not millions, of chunks); a real production system with a much larger KB might
  revisit this.
- The embedding dimension (1536, matching `text-embedding-3-small`) is baked into the frozen schema
  (`db/init/01_schema.sql`) — changing embedding models means a schema migration, not just a config
  flag (wiki/gotchas.md #5). This bit directly in Phase 5: Gemini's embedding model needed its
  `outputDimensionality` parameter set explicitly to 1536 to match, and no common local Ollama
  embedding model happens to output 1536 natively at all.

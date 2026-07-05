CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,                  -- telegram | webform
  external_ref TEXT,
  subject TEXT,
  body TEXT NOT NULL,
  lang TEXT,
  category TEXT,                         -- billing | technical | account | other
  priority TEXT,                         -- low | normal | high | urgent
  sentiment TEXT,
  confidence NUMERIC,
  status TEXT NOT NULL DEFAULT 'new',    -- new | drafted | needs_human | answered | escalated | closed
  auto_resolved BOOLEAN DEFAULT FALSE,
  last_reminder_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (source, external_ref)
);

CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id UUID REFERENCES tickets(id),
  role TEXT NOT NULL,                    -- customer | ai_draft | operator | system
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE kb_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE kb_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES kb_documents(id),
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536)
);
CREATE INDEX ON kb_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE llm_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id UUID,
  purpose TEXT NOT NULL,                 -- classify | answer | self_check | summarize | embed
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  tokens_in INT, tokens_out INT,
  cost_usd NUMERIC(10,6),
  latency_ms INT,
  success BOOLEAN,
  created_at TIMESTAMPTZ DEFAULT now()
);

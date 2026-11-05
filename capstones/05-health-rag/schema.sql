-- The health RAG store: one row per numbered paragraph of the six guideline booklets.
-- Run against the health_rag database (not the task API's database):
--   docker exec -i pg psql -U postgres -d health_rag < capstones/05-health-rag/schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS paragraphs (
    booklet   int  NOT NULL CHECK (booklet BETWEEN 1 AND 6),
    para_no   int  NOT NULL CHECK (para_no >= 1),  -- restarts at 1 in each booklet
    text      text NOT NULL,                       -- cleaned; '' where the original held only an image
    -- Kept up to date by Postgres itself. 'english' stems words: "vaccinate" matches "vaccination".
    tsv       tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding vector(384),                          -- all-MiniLM-L6-v2; filled by embed.py (step 5)
    PRIMARY KEY (booklet, para_no)                  -- a Train.csv label (booklet, number) is one row
);

-- GIN is the index type for full-text search on tsvector.
CREATE INDEX IF NOT EXISTS paragraphs_tsv_idx ON paragraphs USING gin (tsv);

-- No vector index yet: 5,226 rows are few enough for exact search, which is also exact recall.
-- Add HNSW (CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)) only if timing shows a need.
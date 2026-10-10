-- M2: lexical (full-text) and semantic (vector) search.

CREATE EXTENSION IF NOT EXISTS vector;

-- Lexical half: a stored tsvector, title weighted above abstract. English stemming, because the
-- documents are English; non-English queries rely on the multilingual embeddings instead.
ALTER TABLE papers
    ADD COLUMN search_tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', title), 'A') ||
        setweight(to_tsvector('english', abstract), 'B')
    ) STORED;
CREATE INDEX papers_search_tsv_idx ON papers USING gin (search_tsv);

-- Semantic half: one embedding per paper and model. A separate table so changing the model
-- (or its dimension) is a new table, not a rewrite of papers.
CREATE TABLE paper_embeddings (
    arxiv_id     text        PRIMARY KEY REFERENCES papers (arxiv_id) ON DELETE CASCADE,
    model        text        NOT NULL,
    embedding    vector(1024) NOT NULL,             -- bge-m3 dense output
    embedded_at  timestamptz NOT NULL DEFAULT now() -- re-embed when papers.modified_at is newer
);

-- HNSW: approximate nearest neighbours, no training step, handles inserts as they come.
-- Cosine distance because bge-m3 is trained for cosine similarity.
CREATE INDEX paper_embeddings_hnsw_idx ON paper_embeddings
    USING hnsw (embedding vector_cosine_ops);

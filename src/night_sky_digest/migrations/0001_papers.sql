-- arXiv metadata (CC0). Abstracts only, never full text.
CREATE TABLE papers (
    arxiv_id          text PRIMARY KEY,           -- e.g. 2406.10062 or astro-ph/0601001
    title             text        NOT NULL,
    abstract          text        NOT NULL,
    authors           text[]      NOT NULL,
    categories        text[]      NOT NULL,       -- first one is the primary category
    primary_category  text        NOT NULL,
    created           date        NOT NULL,       -- v1 submission
    updated           date,                       -- latest version, if any
    datestamp         date        NOT NULL,       -- last change on arXiv's side (OAI-PMH)
    license           text,
    doi               text,
    comments          text,
    deleted           boolean     NOT NULL DEFAULT false,
    ingested_at       timestamptz NOT NULL DEFAULT now(),  -- first seen
    modified_at       timestamptz NOT NULL DEFAULT now()   -- last real change in this table
);

CREATE INDEX papers_datestamp_idx ON papers (datestamp);
CREATE INDEX papers_primary_category_idx ON papers (primary_category);

-- High-water mark per OAI set: every record with datestamp <= harvested_through is stored.
CREATE TABLE harvest_state (
    set_spec           text PRIMARY KEY,
    harvested_through  date        NOT NULL,
    updated_at         timestamptz NOT NULL DEFAULT now()
);

-- One row per ingest run. Feeds ingest_last_success_timestamp in M5.
CREATE TABLE harvest_runs (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    set_spec     text        NOT NULL,
    from_date    date        NOT NULL,
    until_date   date        NOT NULL,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    status       text        NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    pages        integer     NOT NULL DEFAULT 0,
    inserted     integer     NOT NULL DEFAULT 0,
    updated      integer     NOT NULL DEFAULT 0,
    unchanged    integer     NOT NULL DEFAULT 0,
    deleted      integer     NOT NULL DEFAULT 0,
    error        text
);

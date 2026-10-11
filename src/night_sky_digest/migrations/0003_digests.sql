-- M4: one digest per day. Re-running a day replaces it.
CREATE TABLE digests (
    digest_date  date        PRIMARY KEY,           -- the day the covered papers were submitted
    created_at   timestamptz NOT NULL DEFAULT now(),
    model        text        NOT NULL,
    sections     jsonb       NOT NULL,              -- [{code, title, paper_count, highlights: [...]}]
    markdown     text        NOT NULL,
    stats        jsonb       NOT NULL               -- tokens, latency, retries, dropped highlights
);

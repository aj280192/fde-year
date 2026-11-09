CREATE TABLE IF NOT EXISTS chunks (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    strategy      text    NOT NULL,
    booklet       int     NOT NULL,
    covers        int[]   NOT NULL,          -- the paragraphs this chunk counts as covering
    piece         int     NOT NULL DEFAULT 1, -- 1, 2, 3 … when one paragraph is split
    heading       text,                       -- the nearest heading, as metadata (change f only)
    text          text    NOT NULL,
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    tsv_weighted  tsvector GENERATED ALWAYS AS (
                      setweight(to_tsvector('english', coalesce(heading, '')), 'A')
                   || setweight(to_tsvector('english', text), 'D')) STORED,
    embedding     vector(384),
    UNIQUE (strategy, booklet, covers, piece)
);
CREATE INDEX IF NOT EXISTS chunks_strategy_idx ON chunks (strategy);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_tsv_weighted_idx ON chunks USING gin (tsv_weighted);
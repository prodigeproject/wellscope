-- Search index projected from the JSON outputs; rebuilt on every ingest.
PRAGMA foreign_keys = ON;

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE documents (
  doc_id TEXT PRIMARY KEY,
  doc_type TEXT NOT NULL,
  title TEXT NOT NULL,
  label TEXT NOT NULL,
  well TEXT,
  rig TEXT,
  report_number INTEGER,
  report_date TEXT,
  period_start TEXT,
  period_end TEXT,
  source_file TEXT NOT NULL,
  page_count INTEGER NOT NULL,
  quality_status TEXT NOT NULL,
  summary TEXT NOT NULL,
  rendered TEXT NOT NULL
);

CREATE TABLE fields (
  doc_id TEXT NOT NULL REFERENCES documents (doc_id),
  key TEXT NOT NULL,
  label TEXT NOT NULL,
  section TEXT NOT NULL,
  raw TEXT NOT NULL,
  value REAL,
  unit TEXT,
  date TEXT,
  page INTEGER,
  PRIMARY KEY (doc_id, key)
);

CREATE TABLE operations (
  doc_id TEXT NOT NULL REFERENCES documents (doc_id),
  seq INTEGER NOT NULL,
  op_date TEXT,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  hours REAL,
  phase_code TEXT,
  activity_code TEXT,
  productive_code TEXT,
  npt INTEGER NOT NULL,
  rig_status TEXT,
  md_from_m REAL,
  description TEXT NOT NULL,
  page INTEGER,
  PRIMARY KEY (doc_id, seq)
);

CREATE TABLE glossary (
  id TEXT PRIMARY KEY,
  term TEXT NOT NULL,
  aliases TEXT NOT NULL,
  expansion TEXT,
  description TEXT,
  status TEXT NOT NULL,
  senses TEXT NOT NULL,
  category TEXT NOT NULL,
  source_row INTEGER NOT NULL
);

CREATE TABLE chunks (
  rowid INTEGER PRIMARY KEY,
  chunk_id TEXT NOT NULL UNIQUE,
  doc_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  page INTEGER,
  text TEXT NOT NULL,
  index_text TEXT NOT NULL
);

-- Keeps sizes and values such as 17-1/2 and 10.0ppg whole while stemming English words.
CREATE VIRTUAL TABLE chunks_fts USING fts5 (
  index_text,
  content = 'chunks',
  content_rowid = 'rowid',
  tokenize = "porter unicode61 remove_diacritics 2 tokenchars '.-/'"
);

CREATE TABLE chunk_vectors (
  chunk_id TEXT PRIMARY KEY REFERENCES chunks (chunk_id),
  vector BLOB NOT NULL
);

CREATE TABLE quality_findings (
  doc_id TEXT NOT NULL,
  check_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  ok INTEGER NOT NULL,
  detail TEXT NOT NULL
);

CREATE TABLE conflicts (
  finding_id TEXT NOT NULL,
  detail TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  value TEXT NOT NULL
);

CREATE INDEX idx_documents_date ON documents (report_date);
CREATE INDEX idx_chunks_doc ON chunks (doc_id);

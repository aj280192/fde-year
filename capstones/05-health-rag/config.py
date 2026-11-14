"""Settings for the answering pipeline: one place, imported by index.py and rag.py."""

import os

FINAL_STRATEGY = "headings_split"  # the chunking kept in week 5 (results.csv, run 19)
POOL = 20  # candidates retrieved, then re-ordered by the reranker
TOP_K = 5  # sources given to the model
ABSTAIN_THRESHOLD = (
    -2.0  # the lowest top reranker score that still answers: set in step 6
)
ABSTAIN_TEXT = "cannot find in sources"

LLM_BASE_URL = os.environ.get("HEALTH_RAG_LLM_URL", "http://localhost:11434/v1")
LLM_MODEL = os.environ.get("HEALTH_RAG_MODEL", "qwen3.8:latest")
HEALTH_DB = os.environ.get(
    "HEALTH_RAG_DATABASE_URL", "postgresql://postgres:dev@localhost:5432/health_rag"
)

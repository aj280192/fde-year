#!/usr/bin/env bash
# Week 5 chunking experiments, in a fixed order so the run numbers are predictable.
# Run from capstones/05-health-rag with HEALTH_RAG_DATABASE_URL set, after runs 1 to 5.
#
#   bash run_experiments.sh check            # runs 6 and 7: hybrid_norm, and the chunk-path check
#   bash run_experiments.sh chunks <hybrid>  # runs 8 to 18; <hybrid> is hybrid or hybrid_norm (from run 6)
#
# The reranker and the held-out run are separate commands (see the README), because
# they use whichever setup wins here.
set -euo pipefail

ev() { uv run python evaluate.py "$@"; }

case "${1:-}" in
  check)
    ev --method hybrid_norm --notes "RRF on keyword_norm + vector"                       # run 6
    docker exec -i pg psql -U postgres -d health_rag -q < schema_chunks.sql
    uv run python build_chunks.py --strategy whole
    uv run python embed_chunks.py --strategy whole
    ev --method hybrid --chunking whole --notes "check: must equal run 5"                # run 7
    ;;
  chunks)
    hybrid="${2:?give the hybrid that won run 6: hybrid or hybrid_norm}"
    for s in split headings headings_split heading_meta; do
      uv run python build_chunks.py --strategy "$s"
      uv run python embed_chunks.py --strategy "$s"
    done
    for s in split headings headings_split; do                                           # runs 8 to 16
      ev --method keyword_norm --chunking "$s" --notes "$s"
      ev --method vector       --chunking "$s" --notes "$s"
      ev --method "$hybrid"    --chunking "$s" --notes "$s"
    done
    ev --method keyword_weighted --chunking heading_meta --notes "heading weighted A, text D"  # run 17
    ev --method hybrid_weighted  --chunking heading_meta --notes "heading weighted A, text D"  # run 18
    uv run python results_table.py
    ;;
  *)
    echo "usage: bash run_experiments.sh check | chunks <hybrid|hybrid_norm>" >&2
    exit 2
    ;;
esac

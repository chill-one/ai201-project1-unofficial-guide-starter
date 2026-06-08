"""Evaluate retrieval quality against a small local question set."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from chroma_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_MODEL_NAME,
    DEFAULT_PERSIST_DIR,
    DEFAULT_RERANK_MODEL_NAME,
    count_vectors,
    rerank,
    retrieve,
)


TOKEN_PATTERN = re.compile(r"\b\w+\b|[^\w\s]")

DEFAULT_EVALUATION_QUERIES: list[dict[str, object]] = [
    {
        "question": "What are the top 5 ways Mason graduates found jobs?",
        "expected_terms": [
            "Internships",
            "Handshake",
            "LinkedIn",
            "Indeed",
            "career fairs",
        ],
        "min_matches": 3,
    },
    {
        "question": "What does ASSIP stand for?",
        "expected_terms": ["Aspiring Scientists"],
        "min_matches": 1,
    },
    {
        "question": "What types of financial aid does GMU list on the Scholarships page?",
        "expected_terms": ["Mason Merit Scholarships", "Mason Foundation Scholarships"],
        "min_matches": 1,
    },
    {
        "question": "Name three research Institute listed in GMU's Research Centers directory.",
        "expected_terms": ["Institute for Sustainable Earth", "Digital Innovation"],
        "min_matches": 1,
    },
    {
        "question": "What kinds of funding opportunities does GMU list for graduate students?",
        "expected_terms": ["Research", "Fieldwork", "funding"],
        "min_matches": 1,
    },
]


def count_result_tokens(result: dict[str, Any]) -> int:
    """Return token count for a retrieved result."""
    metadata = result.get("metadata") or {}
    token_count = metadata.get("token_count")
    if isinstance(token_count, int):
        return token_count
    if isinstance(token_count, str) and token_count.isdigit():
        return int(token_count)
    return len(TOKEN_PATTERN.findall(str(result.get("text", ""))))


def load_evaluation_queries(path: Path | None) -> list[dict[str, object]]:
    """Load evaluation questions from JSON or use the default planning set."""
    if path is None:
        return DEFAULT_EVALUATION_QUERIES

    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("Evaluation file must contain a JSON list.")

    queries: list[dict[str, object]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Evaluation item {index} must be an object.")
        question = item.get("question")
        expected_terms = item.get("expected_terms")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Evaluation item {index} needs a question string.")
        if not isinstance(expected_terms, list) or not expected_terms:
            raise ValueError(f"Evaluation item {index} needs expected_terms.")
        queries.append(
            {
                "question": question,
                "expected_terms": [str(term) for term in expected_terms],
                "min_matches": int(item.get("min_matches", 1)),
            }
        )
    return queries


def matched_terms(results: list[dict[str, Any]], expected_terms: list[str]) -> list[str]:
    """Find expected answer terms that appear in retrieved chunk text."""
    retrieved_text = "\n".join(str(result.get("text", "")) for result in results).lower()
    return [term for term in expected_terms if term.lower() in retrieved_text]


def evaluate_queries(
    queries: list[dict[str, object]],
    *,
    top_k: int = 50,
    rerank_top_k: int = 5,
    use_rerank: bool = True,
    persist_dir: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    model_name: str = DEFAULT_MODEL_NAME,
    rerank_model_name: str = DEFAULT_RERANK_MODEL_NAME,
) -> dict[str, object]:
    """Run retrieval evaluation and return aggregate metrics."""
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if rerank_top_k <= 0:
        raise ValueError("rerank_top_k must be greater than 0")

    rows = []
    hit_count = 0
    token_totals = []

    for item in queries:
        question = str(item["question"])
        expected_terms = [str(term) for term in item["expected_terms"]]
        min_matches = int(item.get("min_matches", 1))
        candidates = retrieve(
            question,
            top_k=top_k,
            persist_dir=persist_dir,
            collection_name=collection_name,
            model_name=model_name,
        )
        final_results = (
            rerank(
                question,
                candidates,
                top_k=rerank_top_k,
                model_name=rerank_model_name,
            )
            if use_rerank
            else candidates[:rerank_top_k]
        )
        matches = matched_terms(final_results, expected_terms)
        hit = len(matches) >= min_matches
        if hit:
            hit_count += 1
        token_total = sum(count_result_tokens(result) for result in final_results)
        token_totals.append(token_total)
        rows.append(
            {
                "question": question,
                "hit": hit,
                "matched_terms": matches,
                "expected_terms": expected_terms,
                "tokens_retrieved": token_total,
                "results": final_results,
            }
        )

    query_count = len(queries)
    recall_at_5 = hit_count / query_count if query_count else 0.0
    avg_tokens = sum(token_totals) / query_count if query_count else 0.0
    return {
        "recall@5": recall_at_5,
        "hit_count": hit_count,
        "query_count": query_count,
        "vector_count": count_vectors(
            persist_dir=persist_dir,
            collection_name=collection_name,
        ),
        "avg_tokens_retrieved": avg_tokens,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for retrieval evaluation."""
    parser = argparse.ArgumentParser(
        description="Report recall@5, vector count, and average retrieved tokens."
    )
    parser.add_argument("--eval-file", type=Path)
    parser.add_argument("--top-k", default=50, type=int)
    parser.add_argument("--rerank-top-k", default=5, type=int)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR, type=Path)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--rerank-model-name", default=DEFAULT_RERANK_MODEL_NAME)
    parser.add_argument(
        "--show-chunks",
        action="store_true",
        help="Print returned chunk ids, scores, and excerpts for each query.",
    )
    return parser.parse_args()


def print_report(report: dict[str, object], *, show_chunks: bool = False) -> None:
    """Print a human-readable evaluation report."""
    print(f"recall@5: {report['recall@5']:.3f} ({report['hit_count']}/{report['query_count']})")
    print(f"vector_count: {report['vector_count']}")
    print(f"avg_tokens_retrieved: {report['avg_tokens_retrieved']:.1f}")
    print()

    for index, row in enumerate(report["rows"], start=1):
        status = "hit" if row["hit"] else "miss"
        matched = ", ".join(row["matched_terms"]) or "none"
        print(f"{index}. {status}: {row['question']}")
        print(f"   matched_terms: {matched}")
        print(f"   tokens_retrieved: {row['tokens_retrieved']}")
        if show_chunks:
            for rank, result in enumerate(row["results"], start=1):
                metadata = result.get("metadata") or {}
                source_name = metadata.get("source_name", "unknown")
                chunk_id = result.get("id", metadata.get("chunk_id", "unknown"))
                distance = result.get("distance")
                rerank_score = result.get("rerank_score")
                scores = []
                if isinstance(distance, (int, float)):
                    scores.append(f"distance={distance:.4f}")
                if isinstance(rerank_score, (int, float)):
                    scores.append(f"rerank={rerank_score:.4f}")
                excerpt = re.sub(r"\s+", " ", str(result.get("text", ""))).strip()[:180]
                print(f"   [{rank}] {source_name} | {chunk_id} | {' '.join(scores)}")
                print(f"       {excerpt}")
        print()


def main() -> int:
    """Run retrieval evaluation from the command line."""
    args = parse_args()
    try:
        queries = load_evaluation_queries(args.eval_file)
        report = evaluate_queries(
            queries,
            top_k=args.top_k,
            rerank_top_k=args.rerank_top_k,
            use_rerank=not args.no_rerank,
            persist_dir=args.persist_dir,
            collection_name=args.collection_name,
            model_name=args.model_name,
            rerank_model_name=args.rerank_model_name,
        )
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print_report(report, show_chunks=args.show_chunks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

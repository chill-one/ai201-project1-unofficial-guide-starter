"""End-to-end grounded RAG question answering."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

from chroma_store import rerank, retrieve


DEFAULT_TOP_K = 50
DEFAULT_RERANK_TOP_K = 5
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
UNKNOWN_ANSWER = "I don't know based on the retrieved documents."

SYSTEM_PROMPT = """You are a grounded campus opportunities assistant for George Mason University.

Answer the user's question using only the retrieved context below.
If the context does not contain enough information to answer, say: "I don't know based on the retrieved documents."
Do not use outside knowledge.
Do not invent deadlines, eligibility rules, contacts, links, or program details.
Include source attribution in the answer using bracketed source numbers like [1], [2].
Keep the answer concise and directly tied to the user's question.

Output format:
Answer:
<answer with citations>

Sources:
<short source list using the same source numbers>"""


def get_groq_client():
    """Create a Groq API client from the local environment."""
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_key_here":
        raise RuntimeError("Set GROQ_API_KEY in .env before asking questions.")
    return Groq(api_key=api_key)


def format_source(result: dict[str, Any], index: int) -> str:
    """Format one retrieved result for source display."""
    metadata = result.get("metadata") or {}
    source_name = metadata.get("source_name", "unknown source")
    chunk_id = result.get("id") or metadata.get("chunk_id", "unknown chunk")
    distance = result.get("distance")
    rerank_score = result.get("rerank_score")
    parts = [f"[{index}] {source_name}", str(chunk_id)]
    if isinstance(distance, (int, float)):
        parts.append(f"distance={distance:.4f}")
    if isinstance(rerank_score, (int, float)):
        parts.append(f"rerank={rerank_score:.4f}")
    return " | ".join(parts)


def format_context(results: list[dict[str, Any]]) -> str:
    """Format retrieved chunks as numbered snippets for the prompt."""
    snippets = []
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        source_name = metadata.get("source_name", "unknown source")
        chunk_id = result.get("id") or metadata.get("chunk_id", "unknown chunk")
        distance = result.get("distance")
        distance_text = f"{distance:.4f}" if isinstance(distance, (int, float)) else "unknown"
        rerank_score = result.get("rerank_score")
        rerank_text = (
            f" | Rerank score: {rerank_score:.4f}"
            if isinstance(rerank_score, (int, float))
            else ""
        )
        text = str(result.get("text", "")).strip()
        snippets.append(
            f"[{index}] Source: {source_name} | Chunk: {chunk_id} | "
            f"Distance: {distance_text}{rerank_text}\n{text}"
        )
    return "\n\n".join(snippets)


def build_user_prompt(question: str, results: list[dict[str, Any]]) -> str:
    """Build the user message with question and retrieved context."""
    return (
        f"Question:\n{question.strip()}\n\n"
        f"Retrieved context:\n{format_context(results)}"
    )


def extract_answer(content: str) -> str:
    """Extract the answer section from the model's formatted response."""
    content = content.strip()
    match = re.search(
        r"(?is)^\s*Answer:\s*(.*?)(?:\n\s*Sources:\s*.*)?$",
        content,
    )
    if match:
        return match.group(1).strip()
    return content


def ask(
    question: str,
    top_k: int = DEFAULT_TOP_K,
    rerank_top_k: int = DEFAULT_RERANK_TOP_K,
) -> dict[str, object]:
    """Answer a question using retrieved context and Groq generation.

    Args:
        question: User question.
        top_k: Number of initial chunks to retrieve from ChromaDB.
        rerank_top_k: Number of cross-encoder reranked chunks to use as
            generation context.

    Returns:
        A dictionary containing the grounded answer, source list, and raw chunks.
    """
    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    load_dotenv()
    candidates = retrieve(question, top_k=top_k)
    if not candidates:
        return {"answer": UNKNOWN_ANSWER, "sources": [], "chunks": []}
    results = rerank(question, candidates, top_k=rerank_top_k)

    client = get_groq_client()
    model_name = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, results)},
        ],
        temperature=0.1,
        max_tokens=500,
    )
    content = response.choices[0].message.content or ""
    sources = [
        format_source(result, index)
        for index, result in enumerate(results, start=1)
    ]
    return {
        "answer": extract_answer(content),
        "sources": sources,
        "chunks": results,
    }

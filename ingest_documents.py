"""Load local documents, clean text, and produce chunk records."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Iterable

from chroma_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_MODEL_NAME,
    DEFAULT_RERANK_MODEL_NAME,
    DEFAULT_PERSIST_DIR,
    embed_and_index,
    rerank,
    retrieve,
)


SUPPORTED_EXTENSIONS = {".txt", ".md", ".html", ".htm"}
HTML_EXTENSIONS = {".html", ".htm"}
TOKEN_PATTERN = re.compile(r"\b\w+\b|[^\w\s]")


def strip_html(text: str) -> str:
    """Remove HTML markup and noisy page sections from a document.

    Args:
        text: Raw HTML text loaded from a local file.

    Returns:
        Plain text with script/style/navigation-like sections removed, line
        breaks inserted around common block tags, and remaining tags stripped.
    """
    text = re.sub(
        r"(?is)<(script|style|noscript|nav|header|footer|aside).*?>.*?</\1>",
        " ",
        text,
    )
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|section|article|li|h[1-6]|tr)>", "\n\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return text


def clean_text(raw_text: str, *, is_html: bool = False) -> str:
    """Convert raw document content into normalized paragraph text.

    Args:
        raw_text: File contents before cleanup.
        is_html: Whether to strip HTML tags and page boilerplate before
            normalizing whitespace.

    Returns:
        Cleaned text with HTML entities decoded, non-breaking spaces converted,
        blank paragraphs removed, and paragraphs separated by double newlines.
    """
    text = strip_html(raw_text) if is_html else raw_text
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    paragraphs = re.split(r"\n\s*\n+", text)
    cleaned_paragraphs: list[str] = []
    for paragraph in paragraphs:
        paragraph = re.sub(r"[ \t\f\v]+", " ", paragraph)
        paragraph = re.sub(r"\n+", " ", paragraph)
        paragraph = paragraph.strip()
        if paragraph:
            cleaned_paragraphs.append(paragraph)

    return "\n\n".join(cleaned_paragraphs)


def split_paragraphs(text: str) -> list[str]:
    """Split cleaned text into non-empty paragraph blocks.

    Args:
        text: Cleaned document text, usually produced by ``clean_text``.

    Returns:
        A list of stripped paragraphs. Empty or whitespace-only paragraphs are
        omitted.
    """
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", text) if paragraph.strip()]


def count_tokens(text: str) -> int:
    """Count lightweight word and punctuation tokens in a chunk.

    This is a deterministic local tokenizer used only for filtering very short
    chunks. It does not try to match a model tokenizer exactly; words and
    standalone punctuation marks each count as one token.

    Args:
        text: Chunk text to measure.

    Returns:
        Number of lightweight tokens found in the text.
    """
    return len(TOKEN_PATTERN.findall(text))


def chunk_text(text: str, *, chunk_size: int = 300, overlap: int = 60) -> list[str]:
    """Split cleaned text into overlapping character-based chunks.

    The chunker first packs paragraph blocks together when they fit within
    ``chunk_size``. Paragraphs that are too long are split into smaller
    character segments. After segmentation, each chunk after the first starts
    with up to ``overlap`` trailing characters from the previous chunk.

    Args:
        text: Cleaned text to split.
        chunk_size: Maximum number of characters allowed in each final chunk.
        overlap: Number of characters to repeat from the previous chunk.

    Returns:
        Ordered chunk strings, each at or below ``chunk_size`` characters.

    Raises:
        ValueError: If ``chunk_size`` is not positive, ``overlap`` is negative,
            or ``overlap`` is greater than or equal to ``chunk_size``.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return []

    continuation_capacity = chunk_size - overlap
    if overlap and continuation_capacity > 2:
        continuation_capacity -= 2

    segments: list[str] = []
    current = ""

    def current_capacity() -> int:
        return chunk_size if not segments else continuation_capacity

    def emit_segment(segment: str) -> None:
        segment = segment.strip()
        if segment:
            segments.append(segment)

    def emit_current() -> None:
        nonlocal current
        emit_segment(current)
        current = ""

    for paragraph in paragraphs:
        remaining = paragraph
        while remaining:
            capacity = current_capacity()

            if current:
                candidate = f"{current}\n\n{remaining}"
                if len(candidate) <= capacity:
                    current = candidate
                    break
                emit_current()
                continue

            if len(remaining) <= capacity:
                current = remaining
                break

            emit_segment(remaining[:capacity])
            remaining = remaining[capacity:].lstrip()

    if current:
        emit_current()

    chunks: list[str] = []
    for segment in segments:
        if not chunks or overlap == 0:
            chunks.append(segment)
            continue

        prefix = chunks[-1][-min(overlap, len(chunks[-1])) :]
        separator = "\n\n" if len(prefix) + 2 + len(segment) <= chunk_size else ""
        chunks.append(f"{prefix}{separator}{segment}")

    return chunks


def iter_document_paths(input_dir: Path) -> Iterable[Path]:
    """Yield all files under an input directory in stable sorted order.

    Args:
        input_dir: Directory to scan recursively.

    Returns:
        An iterable of file paths. Directories are excluded.
    """
    return sorted(path for path in input_dir.rglob("*") if path.is_file())


def load_document(path: Path) -> str:
    """Read a local document as UTF-8 text.

    Args:
        path: File path to read.

    Returns:
        File contents as text. Invalid UTF-8 bytes are replaced instead of
        raising an error so ingestion can continue across imperfect documents.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_document(
    path: Path,
    *,
    input_dir: Path,
    chunk_size: int,
    overlap: int,
    min_chunk_tokens: int = 0,
) -> list[dict[str, object]]:
    """Load, clean, chunk, and annotate one supported document.

    Args:
        path: Document file to process.
        input_dir: Root input directory, used to create a relative source path.
        chunk_size: Maximum character length for each chunk.
        overlap: Character overlap between consecutive chunks.
        min_chunk_tokens: Drop chunks with fewer than this many lightweight
            tokens after chunking. Use ``0`` to keep every chunk.

    Returns:
        A list of JSON-serializable chunk records. Each record includes chunk
        text, source metadata, chunk settings, character count, and token count.
    """
    raw_text = load_document(path)
    cleaned = clean_text(raw_text, is_html=path.suffix.lower() in HTML_EXTENSIONS)
    chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)
    source_path = path.relative_to(input_dir.parent).as_posix()

    records: list[dict[str, object]] = []
    kept_chunks = [chunk for chunk in chunks if count_tokens(chunk) >= min_chunk_tokens]
    for index, chunk in enumerate(kept_chunks, start=1):
        token_count = count_tokens(chunk)
        records.append(
            {
                "chunk_id": f"{path.name}::{index:04d}",
                "text": chunk,
                "source_path": source_path,
                "source_name": path.name,
                "chunk_index": index,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "char_count": len(chunk),
                "token_count": token_count,
            }
        )

    return records


def ingest_documents(
    input_dir: Path,
    *,
    chunk_size: int = 300,
    overlap: int = 60,
    min_chunk_tokens: int = 0,
) -> tuple[list[dict[str, object]], int, int]:
    """Process a directory of local documents and return chunk records.

    Supported files are cleaned and chunked in memory. Unsupported files are
    skipped with a warning to stderr.

    Args:
        input_dir: Directory containing local source documents.
        chunk_size: Maximum character length for each chunk.
        overlap: Character overlap between consecutive chunks.
        min_chunk_tokens: Drop chunks with fewer than this many lightweight
            tokens after chunking. Use ``0`` to keep every chunk.

    Returns:
        A tuple of ``(records, supported_files, skipped_files)``. ``records``
        contains JSON-serializable chunk dictionaries.

    Raises:
        FileNotFoundError: If ``input_dir`` does not exist.
        NotADirectoryError: If ``input_dir`` is not a directory.
        ValueError: If chunking or filtering settings are invalid.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")
    if min_chunk_tokens < 0:
        raise ValueError("min_chunk_tokens must be greater than or equal to 0")

    supported_files = 0
    skipped_files = 0
    records: list[dict[str, object]] = []

    for path in iter_document_paths(input_dir):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"Skipping unsupported file: {path}", file=sys.stderr)
            skipped_files += 1
            continue

        supported_files += 1
        records.extend(
            chunk_document(
                path,
                input_dir=input_dir,
                chunk_size=chunk_size,
                overlap=overlap,
                min_chunk_tokens=min_chunk_tokens,
            )
        )

    return records, supported_files, skipped_files


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the ingestion script.

    Returns:
        Parsed CLI arguments for indexing or querying.
    """
    parser = argparse.ArgumentParser(
        description="Load local documents, index them in ChromaDB, and retrieve chunks."
    )
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument("--input-dir", default="documents", type=Path)
    parser.add_argument("--chunk-size", default=300, type=int)
    parser.add_argument("--overlap", default=60, type=int)
    parser.add_argument(
        "--min-chunk-tokens",
        default=0,
        type=int,
        help="Drop chunks with fewer than this many lightweight tokens. Default keeps all chunks.",
    )
    parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR, type=Path)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--batch-size", default=64, type=int)
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Add to the existing Chroma collection instead of rebuilding it.",
    )

    query_parser = subparsers.add_parser("query", help="Retrieve chunks from ChromaDB.")
    query_parser.add_argument("query")
    query_parser.add_argument("--top-k", default=50, type=int)
    query_parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR, type=Path)
    query_parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    query_parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    query_parser.add_argument("--rerank-model-name", default=DEFAULT_RERANK_MODEL_NAME)
    query_parser.add_argument("--rerank-top-k", default=5, type=int)
    query_parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Return raw Chroma retrieval results without cross-encoder reranking.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the document indexing or retrieval command-line workflow.

    Returns:
        Process exit code. Returns ``0`` on success and ``1`` when validation
        or filesystem setup fails.
    """
    args = parse_args()
    try:
        if args.command == "query":
            results = retrieve(
                args.query,
                top_k=args.top_k,
                persist_dir=args.persist_dir,
                collection_name=args.collection_name,
                model_name=args.model_name,
            )
            if not args.no_rerank:
                results = rerank(
                    args.query,
                    results,
                    top_k=args.rerank_top_k,
                    model_name=args.rerank_model_name,
                )
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0

        chunks, supported_files, skipped_files = ingest_documents(
            args.input_dir,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            min_chunk_tokens=args.min_chunk_tokens,
        )
        indexed_count = embed_and_index(
            chunks,
            persist_dir=args.persist_dir,
            collection_name=args.collection_name,
            model_name=args.model_name,
            batch_size=args.batch_size,
            reset=not args.no_reset,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(
        f"Indexed {indexed_count} chunks from {supported_files} supported files "
        f"into {args.persist_dir}/{args.collection_name} ({skipped_files} skipped)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

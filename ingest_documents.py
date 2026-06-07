"""Load local documents, clean text, and write character-based JSONL chunks."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Iterable


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
    min_chunk_tokens: int = 11,
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
    output_path: Path,
    *,
    chunk_size: int = 300,
    overlap: int = 60,
    min_chunk_tokens: int = 0,
) -> tuple[int, int, int]:
    """Process a directory of local documents and write JSONL chunk records.

    Supported files are cleaned, chunked, and written as one JSON object per
    line. Unsupported files are skipped with a warning to stderr.

    Args:
        input_dir: Directory containing local source documents.
        output_path: JSONL file to create or overwrite.
        chunk_size: Maximum character length for each chunk.
        overlap: Character overlap between consecutive chunks.
        min_chunk_tokens: Drop chunks with fewer than this many lightweight
            tokens after chunking. Use ``0`` to keep every chunk.

    Returns:
        A tuple of ``(supported_files, skipped_files, chunk_count)``.

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
    chunk_count = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for path in iter_document_paths(input_dir):
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                print(f"Skipping unsupported file: {path}", file=sys.stderr)
                skipped_files += 1
                continue

            supported_files += 1
            records = chunk_document(
                path,
                input_dir=input_dir,
                chunk_size=chunk_size,
                overlap=overlap,
                min_chunk_tokens=min_chunk_tokens,
            )
            for record in records:
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            chunk_count += len(records)

    return supported_files, skipped_files, chunk_count


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the ingestion script.

    Returns:
        Parsed CLI arguments containing the input directory, output path,
        chunk size, and overlap settings.
    """
    parser = argparse.ArgumentParser(
        description="Load local documents, clean text, and write JSONL chunks."
    )
    parser.add_argument("--input-dir", default="documents", type=Path)
    parser.add_argument("--output", default="chunks.jsonl", type=Path)
    parser.add_argument("--chunk-size", default=300, type=int)
    parser.add_argument("--overlap", default=60, type=int)
    parser.add_argument(
        "--min-chunk-tokens",
        default=0,
        type=int,
        help="Drop chunks with fewer than this many lightweight tokens. Default keeps all chunks.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the document ingestion command-line workflow.

    Returns:
        Process exit code. Returns ``0`` on success and ``1`` when validation
        or filesystem setup fails.
    """
    args = parse_args()
    try:
        supported_files, skipped_files, chunk_count = ingest_documents(
            args.input_dir,
            args.output,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            min_chunk_tokens=args.min_chunk_tokens,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(
        f"Wrote {chunk_count} chunks from {supported_files} supported files "
        f"to {args.output} ({skipped_files} skipped)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

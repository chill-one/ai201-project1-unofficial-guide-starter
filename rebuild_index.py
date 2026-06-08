"""Rebuild the ChromaDB index from local documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chroma_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_MODEL_NAME,
    DEFAULT_PERSIST_DIR,
    embed_and_index,
)
from ingest_documents import ingest_documents


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for rebuilding the vector index."""
    parser = argparse.ArgumentParser(
        description="Clean, chunk, embed, and index local documents in ChromaDB."
    )
    parser.add_argument("--input-dir", default="documents", type=Path)
    parser.add_argument("--chunk-size", default=1000, type=int)
    parser.add_argument("--overlap", default=150, type=int)
    parser.add_argument("--min-chunk-tokens", default=0, type=int)
    parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR, type=Path)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--batch-size", default=64, type=int)
    return parser.parse_args()


def rebuild_index(
    *,
    input_dir: Path = Path("documents"),
    chunk_size: int = 1000,
    overlap: int = 150,
    min_chunk_tokens: int = 0,
    persist_dir: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = 64,
) -> dict[str, object]:
    """Clean, chunk, embed, and replace the local ChromaDB index.

    Args:
        input_dir: Directory containing source documents.
        chunk_size: Maximum chunk size in characters.
        overlap: Character overlap between consecutive chunks.
        min_chunk_tokens: Drop chunks with fewer than this many lightweight tokens.
        persist_dir: ChromaDB persistence directory.
        collection_name: ChromaDB collection name.
        model_name: Sentence Transformers embedding model name.
        batch_size: Number of chunks to embed per batch.

    Returns:
        Summary metadata for the rebuild operation.
    """
    chunks, supported_files, skipped_files = ingest_documents(
        input_dir,
        chunk_size=chunk_size,
        overlap=overlap,
        min_chunk_tokens=min_chunk_tokens,
    )
    indexed_count = embed_and_index(
        chunks,
        persist_dir=persist_dir,
        collection_name=collection_name,
        model_name=model_name,
        batch_size=batch_size,
        reset=True,
    )
    return {
        "indexed_count": indexed_count,
        "supported_files": supported_files,
        "skipped_files": skipped_files,
        "persist_dir": str(persist_dir),
        "collection_name": collection_name,
    }


def main() -> int:
    """Run the rebuild workflow and print a concise indexing report."""
    args = parse_args()
    try:
        report = rebuild_index(
            input_dir=args.input_dir,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            min_chunk_tokens=args.min_chunk_tokens,
            persist_dir=args.persist_dir,
            collection_name=args.collection_name,
            model_name=args.model_name,
            batch_size=args.batch_size,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(
        f"Indexed {report['indexed_count']} chunks from "
        f"{report['supported_files']} supported files into "
        f"{report['persist_dir']}/{report['collection_name']} "
        f"({report['skipped_files']} skipped)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

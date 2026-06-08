"""ChromaDB indexing and retrieval helpers for chunk records."""

from __future__ import annotations

from pathlib import Path


DEFAULT_PERSIST_DIR = Path("chroma_db")
DEFAULT_COLLECTION_NAME = "gmu_opportunities"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_model(model_name: str):
    """Load the SentenceTransformer embedding model.

    Args:
        model_name: Sentence Transformers model name or local path.

    Returns:
        A loaded SentenceTransformer model.
    """
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except TypeError:
        return SentenceTransformer(model_name)


def get_chroma_client(persist_dir: Path):
    """Create a persistent ChromaDB client.

    Args:
        persist_dir: Directory where ChromaDB should persist its index files.

    Returns:
        A ChromaDB PersistentClient.
    """
    import chromadb

    return chromadb.PersistentClient(path=str(persist_dir))


def _as_embedding_list(embeddings) -> list[list[float]]:
    """Convert model output into plain Python embedding lists."""
    if hasattr(embeddings, "tolist"):
        embeddings = embeddings.tolist()
    return [[float(value) for value in embedding] for embedding in embeddings]


def _chunk_metadata(chunk: dict[str, object]) -> dict[str, str | int | float | bool]:
    """Build Chroma-compatible metadata from a chunk record."""
    metadata: dict[str, str | int | float | bool] = {}
    for key, value in chunk.items():
        if key == "text":
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        elif value is not None:
            metadata[key] = str(value)
    return metadata


def embed_and_index(
    chunks: list[dict[str, object]],
    *,
    persist_dir: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = 64,
    reset: bool = True,
) -> int:
    """Embed chunk records and store them in a persistent ChromaDB collection.

    Args:
        chunks: Chunk dictionaries returned by ``ingest_documents``.
        persist_dir: Directory for persistent ChromaDB storage.
        collection_name: ChromaDB collection to create or update.
        model_name: Sentence Transformers model used for document embeddings.
        batch_size: Number of chunks to embed and add per Chroma batch.
        reset: Whether to delete and rebuild the collection before indexing.

    Returns:
        Number of chunks indexed.

    Raises:
        ValueError: If ``batch_size`` is not positive or a chunk is missing text.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = get_chroma_client(persist_dir)
    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    model = get_embedding_model(model_name)

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        ids = [str(chunk["chunk_id"]) for chunk in batch]
        documents = []
        for chunk in batch:
            text = chunk.get("text")
            if not isinstance(text, str) or not text:
                raise ValueError(f"Chunk {chunk.get('chunk_id')} is missing text")
            documents.append(text)

        embeddings = _as_embedding_list(
            model.encode(documents, normalize_embeddings=True)
        )
        metadatas = [_chunk_metadata(chunk) for chunk in batch]
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    return len(chunks)


def retrieve(
    query: str,
    *,
    top_k: int = 50,
    persist_dir: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    model_name: str = DEFAULT_MODEL_NAME,
) -> list[dict[str, object]]:
    """Retrieve semantically similar chunks from ChromaDB.

    Args:
        query: Natural-language search query.
        top_k: Maximum number of chunks to return.
        persist_dir: Directory where the ChromaDB index is stored.
        collection_name: ChromaDB collection to query.
        model_name: Sentence Transformers model used for query embeddings.

    Returns:
        Ranked retrieval results. Each result contains ``id``, ``text``,
        ``metadata``, and ``distance``.

    Raises:
        ValueError: If ``query`` is empty or ``top_k`` is not positive.
    """
    if not query.strip():
        raise ValueError("query must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    client = get_chroma_client(persist_dir)
    collection = client.get_collection(collection_name)
    model = get_embedding_model(model_name)
    query_embedding = _as_embedding_list(
        model.encode([query], normalize_embeddings=True)
    )[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved: list[dict[str, object]] = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for result_id, document, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        retrieved.append(
            {
                "id": result_id,
                "text": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return retrieved

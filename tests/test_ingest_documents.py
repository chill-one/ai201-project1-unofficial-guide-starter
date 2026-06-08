import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chroma_store import count_vectors, embed_and_index, rerank, retrieve
from ingest_documents import clean_text, chunk_text, count_tokens, ingest_documents

try:
    import chromadb  # noqa: F401

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class FakeEmbeddingModel:
    def encode(self, texts, normalize_embeddings=True):
        embeddings = []
        for text in texts:
            lower_text = text.lower()
            if "assip" in lower_text or "aspiring scientists" in lower_text:
                embeddings.append([1.0, 0.0, 0.0])
            elif "scholarship" in lower_text:
                embeddings.append([0.0, 1.0, 0.0])
            else:
                embeddings.append([0.0, 0.0, 1.0])
        return embeddings


class FakeRerankModel:
    def predict(self, pairs):
        scores = []
        for _query, text in pairs:
            if "Aspiring Scientists" in text:
                scores.append(10.0)
            elif "Scholarship" in text:
                scores.append(2.0)
            else:
                scores.append(0.5)
        return scores


class IngestDocumentsTest(unittest.TestCase):
    def test_clean_text_strips_html_and_decodes_entities(self):
        raw_html = """
        <html><body>
          <nav>Navigation</nav>
          <h1>Scholarships &amp; Aid</h1>
          <p>Apply&nbsp;today.</p>
          <script>ignored()</script>
        </body></html>
        """

        cleaned = clean_text(raw_html, is_html=True)

        self.assertIn("Scholarships & Aid", cleaned)
        self.assertIn("Apply today.", cleaned)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("ignored()", cleaned)

    def test_chunk_text_returns_no_chunks_for_empty_text(self):
        self.assertEqual(chunk_text(" \n\n\t ", chunk_size=50, overlap=10), [])

    def test_count_tokens_uses_words_and_punctuation(self):
        self.assertEqual(count_tokens("Apply today."), 3)

    def test_chunk_text_respects_size_and_overlap(self):
        text = "A" * 80 + "\n\n" + "B" * 80 + "\n\n" + "C" * 80

        chunks = chunk_text(text, chunk_size=100, overlap=20)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))
        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(previous[-20:], current[:20])

    def test_ingest_documents_returns_records_for_supported_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "documents"
            input_dir.mkdir()

            (input_dir / "aid.txt").write_text("Aid eligibility details." * 10, encoding="utf-8")
            (input_dir / "research.md").write_text("# Research\n\nOpen lab roles." * 10, encoding="utf-8")
            (input_dir / "study.html").write_text(
                "<h1>Study Abroad</h1><p>Programs &amp; deadlines.</p>" * 10,
                encoding="utf-8",
            )
            (input_dir / "ignore.pdf").write_text("unsupported", encoding="utf-8")
            (input_dir / "blank.txt").write_text("   \n\n", encoding="utf-8")

            records, supported, skipped = ingest_documents(
                input_dir,
                chunk_size=120,
                overlap=20,
            )

            self.assertEqual(supported, 4)
            self.assertEqual(skipped, 1)
            self.assertGreater(len(records), 0)
            self.assertTrue(all(record["char_count"] <= 120 for record in records))
            self.assertTrue(any(record["source_name"] == "aid.txt" for record in records))
            self.assertTrue(any(record["source_name"] == "research.md" for record in records))
            self.assertTrue(any(record["source_name"] == "study.html" for record in records))
            self.assertFalse(any(record["source_name"] == "blank.txt" for record in records))

            required_keys = {
                "chunk_id",
                "text",
                "source_path",
                "source_name",
                "chunk_index",
                "chunk_size",
                "overlap",
                "char_count",
                "token_count",
            }
            self.assertTrue(required_keys.issubset(records[0].keys()))

    def test_ingest_documents_filters_chunks_below_min_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "documents"
            input_dir.mkdir()

            (input_dir / "sample.txt").write_text(
                "Tiny\n\none two three four five six seven eight nine ten",
                encoding="utf-8",
            )

            records, supported, skipped = ingest_documents(
                input_dir,
                chunk_size=20,
                overlap=0,
                min_chunk_tokens=2,
            )

            self.assertEqual(supported, 1)
            self.assertEqual(skipped, 0)
            self.assertTrue(records)
            self.assertTrue(all(record["token_count"] >= 2 for record in records))
            self.assertFalse(any(record["text"] == "Tiny" for record in records))

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb is not installed")
    def test_embed_and_index_stores_chunks_in_chroma(self):
        chunks = [
            {
                "chunk_id": "research.txt::0001",
                "text": "ASSIP means Aspiring Scientists Summer Internship Program.",
                "source_path": "documents/research.txt",
                "source_name": "research.txt",
                "chunk_index": 1,
                "chunk_size": 300,
                "overlap": 60,
                "char_count": 58,
                "token_count": 8,
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("chroma_store.get_embedding_model", return_value=FakeEmbeddingModel()):
                indexed_count = embed_and_index(
                    chunks,
                    persist_dir=Path(tmpdir),
                    collection_name="test_collection",
                )
                results = retrieve(
                    "What does ASSIP stand for?",
                    top_k=1,
                    persist_dir=Path(tmpdir),
                    collection_name="test_collection",
                )
                vector_count = count_vectors(
                    persist_dir=Path(tmpdir),
                    collection_name="test_collection",
                )

        self.assertEqual(indexed_count, 1)
        self.assertEqual(vector_count, 1)
        self.assertEqual(results[0]["id"], "research.txt::0001")
        self.assertIn("Aspiring Scientists", results[0]["text"])
        self.assertEqual(results[0]["metadata"]["source_name"], "research.txt")

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb is not installed")
    def test_retrieve_returns_most_relevant_chunk(self):
        chunks = [
            {
                "chunk_id": "research.txt::0001",
                "text": "ASSIP means Aspiring Scientists Summer Internship Program.",
                "source_path": "documents/research.txt",
                "source_name": "research.txt",
                "chunk_index": 1,
                "chunk_size": 300,
                "overlap": 60,
                "char_count": 58,
                "token_count": 8,
            },
            {
                "chunk_id": "aid.txt::0001",
                "text": "Scholarship applications include merit and foundation awards.",
                "source_path": "documents/aid.txt",
                "source_name": "aid.txt",
                "chunk_index": 1,
                "chunk_size": 300,
                "overlap": 60,
                "char_count": 61,
                "token_count": 8,
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("chroma_store.get_embedding_model", return_value=FakeEmbeddingModel()):
                embed_and_index(
                    chunks,
                    persist_dir=Path(tmpdir),
                    collection_name="test_collection",
                )
                results = retrieve(
                    "ASSIP",
                    top_k=1,
                    persist_dir=Path(tmpdir),
                    collection_name="test_collection",
                )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "research.txt::0001")

    def test_rerank_sorts_by_cross_encoder_score(self):
        results = [
            {
                "id": "aid.txt::0001",
                "text": "Scholarship applications include merit awards.",
                "metadata": {"source_name": "aid.txt"},
                "distance": 0.1,
            },
            {
                "id": "research.txt::0001",
                "text": "ASSIP means Aspiring Scientists Summer Internship Program.",
                "metadata": {"source_name": "research.txt"},
                "distance": 0.5,
            },
        ]

        with patch("chroma_store.get_rerank_model", return_value=FakeRerankModel()):
            reranked = rerank("What does ASSIP stand for?", results, top_k=1)

        self.assertEqual(len(reranked), 1)
        self.assertEqual(reranked[0]["id"], "research.txt::0001")
        self.assertEqual(reranked[0]["rerank_rank"], 1)
        self.assertEqual(reranked[0]["rerank_score"], 10.0)


if __name__ == "__main__":
    unittest.main()

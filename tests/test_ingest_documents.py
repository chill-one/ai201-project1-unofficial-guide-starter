import json
import tempfile
import unittest
from pathlib import Path

from ingest_documents import clean_text, chunk_text, count_tokens, ingest_documents


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

    def test_ingest_documents_writes_jsonl_for_supported_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "documents"
            input_dir.mkdir()
            output_path = root / "chunks.jsonl"

            (input_dir / "aid.txt").write_text("Aid eligibility details." * 10, encoding="utf-8")
            (input_dir / "research.md").write_text("# Research\n\nOpen lab roles." * 10, encoding="utf-8")
            (input_dir / "study.html").write_text(
                "<h1>Study Abroad</h1><p>Programs &amp; deadlines.</p>" * 10,
                encoding="utf-8",
            )
            (input_dir / "ignore.pdf").write_text("unsupported", encoding="utf-8")
            (input_dir / "blank.txt").write_text("   \n\n", encoding="utf-8")

            supported, skipped, chunk_count = ingest_documents(
                input_dir,
                output_path,
                chunk_size=120,
                overlap=20,
            )

            self.assertEqual(supported, 4)
            self.assertEqual(skipped, 1)
            self.assertGreater(chunk_count, 0)

            records = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(len(records), chunk_count)
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
            }
            self.assertTrue(required_keys.issubset(records[0].keys()))

    def test_ingest_documents_filters_chunks_below_min_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "documents"
            input_dir.mkdir()
            output_path = root / "chunks.jsonl"

            (input_dir / "sample.txt").write_text(
                "Tiny\n\none two three four five six seven eight nine ten",
                encoding="utf-8",
            )

            supported, skipped, chunk_count = ingest_documents(
                input_dir,
                output_path,
                chunk_size=20,
                overlap=0,
                min_chunk_tokens=2,
            )

            records = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(supported, 1)
            self.assertEqual(skipped, 0)
            self.assertEqual(chunk_count, len(records))
            self.assertTrue(records)
            self.assertTrue(all(record["token_count"] >= 2 for record in records))
            self.assertFalse(any(record["text"] == "Tiny" for record in records))


if __name__ == "__main__":
    unittest.main()

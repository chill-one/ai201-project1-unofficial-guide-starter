import os
import unittest
from unittest.mock import patch

from query import (
    SYSTEM_PROMPT,
    UNKNOWN_ANSWER,
    ask,
    build_user_prompt,
    extract_answer,
    format_source,
)


class FakeMessage:
    content = "Answer:\nASSIP stands for Aspiring Scientists Program [1].\n\nSources:\n[1] research source"


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeGroqClient:
    def __init__(self):
        self.chat = FakeChat()


def fake_results():
    return [
        {
            "id": "research@research-opportunities.txt::0004",
            "text": "Aspiring Scientists Program (ASSIP) provides research opportunities.",
            "metadata": {
                "source_name": "research@research-opportunities.txt",
                "chunk_id": "research@research-opportunities.txt::0004",
            },
            "distance": 0.12345,
        }
    ]


def fake_reranked_results():
    results = fake_results()
    results[0]["rerank_score"] = 3.25
    results[0]["rerank_rank"] = 1
    return results


class QueryTest(unittest.TestCase):
    def test_extract_answer_returns_answer_section(self):
        content = "Answer:\nUse Handshake [1].\n\nSources:\n[1] careers"
        self.assertEqual(extract_answer(content), "Use Handshake [1].")

    def test_format_source_includes_source_chunk_and_distance(self):
        source = format_source(fake_results()[0], 1)
        self.assertIn("[1]", source)
        self.assertIn("research@research-opportunities.txt", source)
        self.assertIn("distance=0.1235", source)

    def test_format_source_includes_rerank_score_when_present(self):
        source = format_source(fake_reranked_results()[0], 1)
        self.assertIn("rerank=3.2500", source)

    def test_build_user_prompt_includes_numbered_context(self):
        prompt = build_user_prompt("What does ASSIP stand for?", fake_results())
        self.assertIn("Question:", prompt)
        self.assertIn("[1] Source: research@research-opportunities.txt", prompt)
        self.assertIn("Aspiring Scientists Program", prompt)

    def test_ask_returns_answer_sources_and_chunks(self):
        client = FakeGroqClient()
        with patch("query.retrieve", return_value=fake_results()):
            with patch("query.rerank", return_value=fake_reranked_results()) as mock_rerank:
                with patch("query.get_groq_client", return_value=client):
                    with patch.dict(os.environ, {"GROQ_MODEL": "test-model"}):
                        result = ask("What does ASSIP stand for?")

        self.assertEqual(
            result["answer"],
            "ASSIP stands for Aspiring Scientists Program [1].",
        )
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["chunks"], fake_reranked_results())
        mock_rerank.assert_called_once()
        self.assertEqual(mock_rerank.call_args.kwargs["top_k"], 5)
        self.assertEqual(client.chat.completions.kwargs["model"], "test-model")
        self.assertEqual(
            client.chat.completions.kwargs["messages"][0]["content"],
            SYSTEM_PROMPT,
        )

    def test_ask_rejects_empty_question(self):
        with self.assertRaises(ValueError):
            ask("   ")

    def test_ask_returns_unknown_when_no_chunks_are_retrieved(self):
        with patch("query.retrieve", return_value=[]):
            result = ask("What is unavailable?")

        self.assertEqual(result["answer"], UNKNOWN_ANSWER)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["chunks"], [])


if __name__ == "__main__":
    unittest.main()

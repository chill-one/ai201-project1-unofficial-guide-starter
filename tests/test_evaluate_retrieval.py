import unittest
from unittest.mock import patch

from evaluate_retrieval import (
    count_result_tokens,
    evaluate_queries,
    matched_terms,
)


def fake_candidate_results():
    return [
        {
            "id": "research.txt::0001",
            "text": "ASSIP means Aspiring Scientists Summer Internship Program.",
            "metadata": {
                "source_name": "research.txt",
                "token_count": 8,
            },
            "distance": 0.4,
        },
        {
            "id": "aid.txt::0001",
            "text": "Mason Merit Scholarships support eligible students.",
            "metadata": {
                "source_name": "aid.txt",
                "token_count": 7,
            },
            "distance": 0.8,
        },
    ]


class EvaluateRetrievalTest(unittest.TestCase):
    def test_count_result_tokens_prefers_metadata(self):
        self.assertEqual(count_result_tokens(fake_candidate_results()[0]), 8)

    def test_matched_terms_finds_expected_text(self):
        matches = matched_terms(fake_candidate_results(), ["Aspiring Scientists", "missing"])
        self.assertEqual(matches, ["Aspiring Scientists"])

    def test_evaluate_queries_reports_recall_vector_count_and_avg_tokens(self):
        queries = [
            {
                "question": "What does ASSIP stand for?",
                "expected_terms": ["Aspiring Scientists"],
                "min_matches": 1,
            }
        ]

        with patch("evaluate_retrieval.retrieve", return_value=fake_candidate_results()):
            with patch("evaluate_retrieval.rerank", return_value=fake_candidate_results()[:1]):
                with patch("evaluate_retrieval.count_vectors", return_value=2):
                    report = evaluate_queries(queries)

        self.assertEqual(report["recall@5"], 1.0)
        self.assertEqual(report["hit_count"], 1)
        self.assertEqual(report["vector_count"], 2)
        self.assertEqual(report["avg_tokens_retrieved"], 8.0)
        self.assertTrue(report["rows"][0]["hit"])


if __name__ == "__main__":
    unittest.main()

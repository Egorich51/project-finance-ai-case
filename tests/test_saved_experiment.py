import hashlib
import json
import unittest
from pathlib import Path

from src.extraction import evaluate, prepare_input


class SavedExperimentTests(unittest.TestCase):
    def test_response_and_metrics_are_reproducible_without_a_model(self):
        root = Path(__file__).resolve().parents[1]
        case = root / 'case'
        raw = (case / 'model-response.txt').read_text()
        predicted = json.loads(raw)
        self.assertEqual(predicted, json.loads((case / 'extracted.json').read_text()))
        self.assertEqual(raw, json.loads((case / 'ollama-response.json').read_text())['response'])
        result = evaluate(predicted, json.loads((case / 'gold.json').read_text()))
        saved = json.loads((root / 'output/extraction-evaluation.json').read_text())
        for key in result:
            self.assertEqual(result[key], saved[key])
        self.assertEqual(result['fields']['correct'], 1)
        self.assertEqual(result['sources']['correct'], 4)
        self.assertEqual(result['issues']['false_negative'], 2)

    def test_saved_request_matches_only_prompt_and_source_documents(self):
        root = Path(__file__).resolve().parents[1] / 'case'
        request = json.loads((root / 'model-request.json').read_text())
        expected = (root / 'prompt.md').read_text() + '\n\n# Документы\n\n' + prepare_input(root / 'source')
        self.assertEqual(request['prompt'], expected)
        metadata = json.loads((root / 'model-metadata.json').read_text())
        self.assertEqual(hashlib.sha256(expected.encode()).hexdigest(), metadata['prompt_sha256'])
        self.assertNotIn('case_author', expected)

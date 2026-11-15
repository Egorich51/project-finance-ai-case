"""Separate source-only GPU payloads from local gold-based evaluation."""
import hashlib
import json
from pathlib import Path

from src.extraction import evaluate, prepare_input


def build_gpu_inputs(cases_dir: Path) -> list[dict]:
    manifest = json.loads((cases_dir / 'manifest.json').read_text(encoding='utf-8'))
    result = []
    for item in manifest:
        root = cases_dir / item['path']
        text = prepare_input(root / 'source')
        if hashlib.sha256(text.encode()).hexdigest() != item['input_sha256']:
            raise ValueError('Source documents changed after protocol freeze: ' + item['case_id'])
        prompt = (root / 'prompt.md').read_text(encoding='utf-8') + '\n\n# Документы\n\n' + text
        result.append({key: item[key] for key in ('case_id', 'business', 'variant')} | {
            'prompt': prompt, 'input_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        })
    return result


def score_gpu_records(records_dir: Path, cases_dir: Path) -> list[dict]:
    expected = {item['case_id']: item for item in build_gpu_inputs(cases_dir)}
    manifest = {item['case_id']: item for item in json.loads((cases_dir / 'manifest.json').read_text(encoding='utf-8'))}
    results = []
    seen = set()
    for file in sorted(records_dir.rglob('*.json')):
        record = json.loads(file.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or 'case_id' not in record:
            continue
        case_id = record['case_id']
        pair = (record.get('model'), case_id)
        if pair in seen:
            raise ValueError('Duplicate model/case response: ' + str(pair))
        seen.add(pair)
        if case_id not in expected or record.get('input_sha256') != expected[case_id]['input_sha256']:
            raise ValueError('GPU response belongs to a different source/prompt version: ' + str(case_id))
        root = cases_dir / manifest[case_id]['path']
        gold_text = (root / 'gold.json').read_text(encoding='utf-8')
        if hashlib.sha256(gold_text.encode()).hexdigest() != manifest[case_id]['gold_sha256']:
            raise ValueError('Gold changed after protocol freeze: ' + case_id)
        parse_error = record.get('error')
        predicted = {}
        if not parse_error:
            try:
                predicted = json.loads(record.get('raw_text', ''))
                if not isinstance(predicted, dict):
                    raise ValueError('Expected a JSON object')
                if record.get('finish_reason') == 'length':
                    raise ValueError('Generation reached its token limit')
            except (ValueError, TypeError) as error:
                parse_error, predicted = str(error), {}
        results.append({
            'model': record['model'], 'case_id': case_id,
            'business': expected[case_id]['business'], 'variant': expected[case_id]['variant'],
            'parse_error': parse_error,
            'top_level_contract': isinstance(predicted.get('fields'), dict) and isinstance(predicted.get('issues'), list),
            'evaluation': evaluate(predicted, json.loads(gold_text)),
            'elapsed_seconds': record.get('elapsed_seconds'), 'generated_tokens': record.get('generated_tokens'),
            'record': str(file.relative_to(records_dir)),
        })
    return results

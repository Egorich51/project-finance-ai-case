"""Frozen value/period/source checks for the user-supplied industrial archive."""
import hashlib
import json
import math
from pathlib import Path


def evaluate_fields(predicted: dict, reference: dict) -> dict:
    fields = predicted.get('fields', {})
    if not isinstance(fields, dict):
        fields = {}
    correct, grounded, details = 0, 0, []
    factors = {'million_rub': 1.0, 'thousand_rub': 0.001, 'rub': 0.000001}
    for name, target in reference['fields'].items():
        item = fields.get(name, {})
        if not isinstance(item, dict):
            item = {}
        value, unit = item.get('value'), item.get('unit')
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if numeric:
            try:
                numeric = math.isfinite(value)
            except OverflowError:
                numeric = False
        unit_valid = isinstance(unit, str)
        normalized = value
        if unit_valid and target['unit'] == 'million_rub':
            unit_valid = unit in factors
            if numeric and unit_valid:
                normalized = value * factors[unit]
        else:
            unit_valid = unit_valid and unit == target['unit']
        period = item.get('period')
        value_valid = (numeric and unit_valid and type(period) is type(target['period']) and period == target['period']
                       and abs(normalized - target['value']) <= target['tolerance'])
        sources = item.get('sources', [])
        if not isinstance(sources, list):
            sources = []
        source_valid = bool({v for v in sources if isinstance(v, str)} & set(target['allowed_sources']))
        correct += int(value_valid)
        grounded += int(value_valid and source_valid)
        details.append({'field': name, 'value_correct': bool(value_valid), 'source_hit': source_valid,
                        'expected': target['value'], 'actual': value, 'actual_unit': unit, 'actual_period': period,
                        'allowed_sources': target['allowed_sources'], 'actual_sources': sources})
    issues = predicted.get('issues', [])
    if not isinstance(issues, list):
        issues = []
    signals = {(i.get('field'), i.get('kind')) for i in issues if isinstance(i, dict) and isinstance(i.get('field'), str) and isinstance(i.get('kind'), str)}
    return {'values_correct': correct, 'grounded_correct': grounded, 'total': len(reference['fields']),
            'false_issues': len(signals), 'issues': [list(p) for p in sorted(signals)], 'fields': details,
            'unexpected_fields': sorted(set(fields) - set(reference['fields']))}


def score_records(root: Path) -> list[dict]:
    frozen = json.loads((root/'experiment.json').read_text())
    for key, path in [('gpu_inputs_sha256', root/'gpu-inputs.json'),
                      ('reference_sha256', root/'reference.json'),
                      ('runner_sha256', root.parents[1]/'scripts/run_gpu_benchmark.py'),
                      ('source_manifest_sha256', root/'source-manifest.json')]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != frozen[key]:
            raise ValueError('Frozen artifact mismatch: ' + str(path))
    manifest = json.loads((root/'source-manifest.json').read_text())
    for name, digest in manifest['files'].items():
        if hashlib.sha256((root/'input'/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Source artifact mismatch: ' + name)
    if hashlib.sha256((root/'source-archive.zip').read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Source archive mismatch')
    jobs = {j['case_id']: j for j in json.loads((root/'gpu-inputs.json').read_text())}
    references = json.loads((root/'reference.json').read_text())
    records, seen = [], set()
    for path in sorted((root/'results/raw').glob('*/*.json')):
        item = json.loads(path.read_text())
        if 'case_id' not in item:
            continue
        environment = json.loads((path.parent/'environment.json').read_text())
        if item['model'] != environment['model'] or item['revision'] != environment['revision'] or environment['runner_sha256'] != frozen['runner_sha256']:
            raise ValueError('Model environment mismatch')
        key = (item['model'], item['case_id'])
        if key in seen:
            raise ValueError('Duplicate first response: ' + str(key))
        seen.add(key)
        expected = jobs[item['case_id']]
        if item['input_sha256'] != expected['input_sha256'] or hashlib.sha256(expected['prompt'].encode()).hexdigest() != expected['input_sha256']:
            raise ValueError('Input version mismatch')
        error, predicted = item.get('error'), {}
        if not error:
            try:
                predicted = json.loads(item['raw_text'])
                if not isinstance(predicted, dict):
                    raise ValueError('JSON root must be an object')
                if item.get('finish_reason') == 'length':
                    raise ValueError('Generation reached max_new_tokens')
            except (ValueError, TypeError) as exception:
                predicted, error = {}, str(exception)
        records.append({'model': item['model'], 'case_id': item['case_id'], 'parse_error': error,
                        'elapsed_seconds': item.get('elapsed_seconds'), 'generated_tokens': item.get('generated_tokens'),
                        'evaluation': evaluate_fields(predicted, references[item['case_id']]),
                        'record': str(path.relative_to(root))})
    return records

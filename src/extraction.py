"""Document serialization, strict field evaluation and human confirmation gate."""
import math
from pathlib import Path

from docx import Document
from openpyxl import load_workbook


def prepare_input(source_dir: Path) -> str:
    lines = []
    for file in sorted(source_dir.iterdir()):
        if file.suffix == '.docx':
            for index, paragraph in enumerate(Document(file).paragraphs, 1):
                if paragraph.text:
                    lines.append(f'[{file.name}|paragraph:{index}] {paragraph.text}')
        elif file.suffix == '.xlsx':
            workbook = load_workbook(file, data_only=False)
            for sheet in workbook:
                for row in sheet:
                    if not any(cell.value is not None for cell in row):
                        continue
                    for cell in row:
                        value = 'null' if cell.value is None else str(cell.value)
                        lines.append(f'[{file.name}|{sheet.title}!{cell.coordinate}] {value}')
            workbook.close()
    return '\n'.join(lines)


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _normalized(item):
    value, unit = item.get('value'), item.get('unit')
    if value is None:
        return value, unit
    if not _number(value):
        return 'invalid', unit
    scale = {'million_rub': 1, 'thousand_rub': 0.001, 'rub': 0.000001}
    if unit in scale:
        return value * scale[unit], 'million_rub'
    return value, unit


def _same_value(predicted, expected):
    if (not isinstance(predicted, dict) or type(predicted.get('period')) is not type(expected['period'])
            or predicted.get('period') != expected['period']):
        return False
    p_value, p_unit = _normalized(predicted)
    e_value, e_unit = _normalized(expected)
    if p_unit != e_unit:
        return False
    if e_value is None:
        if 'value' not in predicted or p_value is not None:
            return False
    elif not _number(p_value) or abs(p_value - e_value) > 1e-6:
        return False
    if 'candidates' in expected:
        candidates = predicted.get('candidates', [])
        if not isinstance(candidates, list) or len(candidates) != len(expected['candidates']):
            return False
        return all(any(_same_value(candidate, target) for candidate in candidates) for target in expected['candidates'])
    return True


def _sources(item):
    if not isinstance(item, dict) or not isinstance(item.get('sources'), list):
        return set()
    return {(s['file'], s['locator']) for s in item['sources']
            if isinstance(s, dict) and isinstance(s.get('file'), str) and isinstance(s.get('locator'), str)}


def evaluate(predicted: dict, gold: dict) -> dict:
    fields = predicted.get('fields', {})
    if not isinstance(fields, dict):
        fields = {}
    correct, source_correct, source_total = 0, 0, 0
    incorrect = []
    for name, target in gold['fields'].items():
        item = fields.get(name)
        valid = _same_value(item, target)
        correct += int(valid)
        if not valid:
            incorrect.append(name)
        expected_sources = _sources(target)
        source_total += len(expected_sources)
        source_correct += len(expected_sources & _sources(item))
    expected_issues = {(i['field'], i['kind']) for i in gold['issues']}
    issues = predicted.get('issues', [])
    if not isinstance(issues, list):
        issues = []
    actual_issues = {(i['field'], i['kind']) for i in issues
                     if isinstance(i, dict) and isinstance(i.get('field'), str) and isinstance(i.get('kind'), str)}
    total = len(gold['fields'])
    return {
        'fields': {'correct': correct, 'total': total, 'accuracy': correct / total},
        'sources': {'correct': source_correct, 'total': source_total, 'accuracy': source_correct / source_total},
        'issues': {
            'true_positive': len(expected_issues & actual_issues),
            'false_positive': len(actual_issues - expected_issues),
            'false_negative': len(expected_issues - actual_issues),
            'missed': [list(i) for i in sorted(expected_issues - actual_issues)],
            'unexpected': [list(i) for i in sorted(actual_issues - expected_issues)],
        },
        'incorrect_fields': incorrect,
        'unexpected_fields': sorted(set(fields) - set(gold['fields'])),
        'source_metric_note': 'Проверка адресов источников отдельно от правильности значений; не доказывает смысловую поддержку значения источником.',
    }


def validate_confirmed(data: dict) -> list[str]:
    errors = []
    for key in ('budget', 'equity', 'rate', 'years', 'stress_factor', 'dscr_floor'):
        if not _number(data.get(key)):
            errors.append(f'{key}: требуется конечное число; пропуск не заменяется нулём')
    for key in ('budget', 'equity', 'rate'):
        if _number(data.get(key)) and data[key] < 0:
            errors.append(f'{key}: значение должно быть неотрицательным')
    years = data.get('years')
    if _number(years) and (not isinstance(years, int) or years < 1):
        errors.append('years: требуется положительное целое число лет')
    if _number(data.get('stress_factor')) and not 0 <= data['stress_factor'] <= 1:
        errors.append('stress_factor: требуется множитель от 0 до 1')
    if _number(data.get('dscr_floor')) and data['dscr_floor'] <= 0:
        errors.append('dscr_floor: порог должен быть положительным')
    cfads = data.get('cfads')
    if not isinstance(cfads, list) or len(cfads) != years or not all(_number(v) for v in cfads):
        errors.append('cfads: нужен конечный денежный поток для каждого года срока кредита')
    if data.get('unit') != 'million_rub':
        errors.append('unit: расчёт принимает только million_rub')
    resolutions = data.get('resolutions', [])
    if not isinstance(resolutions, list):
        resolutions = []
    for key in ('budget', 'equity'):
        matches = [r for r in resolutions if isinstance(r, dict) and r.get('field') == key]
        if (len(matches) != 1 or matches[0].get('status') != 'confirmed'
                or not matches[0].get('confirmed_by') or not matches[0].get('note')
                or matches[0].get('value') != data.get(key)):
            errors.append(f'{key}: требуется отдельное подтверждение значения и разрешение исходной проблемы')
    return errors

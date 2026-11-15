"""One local Ollama run. Gold is read only after the response is saved."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.extraction import evaluate, prepare_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, default=Path('case'))
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--model', default='qwen2.5:1.5b')
    args = parser.parse_args()
    prompt = (args.case / 'prompt.md').read_text(encoding='utf-8')
    input_text = prepare_input(args.case / 'source')
    (args.case / 'model-input.txt').write_text(input_text + '\n', encoding='utf-8')
    payload = {
        'model': args.model,
        'prompt': prompt + '\n\n# Документы\n\n' + input_text,
        'stream': False,
        'format': 'json',
        'options': {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 4096},
    }
    (args.case / 'model-request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    started = datetime.now(timezone.utc).isoformat()
    request = Request('http://127.0.0.1:11434/api/generate', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=600) as response:
        response_text = response.read().decode()
    (args.case / 'ollama-response.json').write_text(response_text + '\n', encoding='utf-8')
    response = json.loads(response_text)
    raw = response['response']
    (args.case / 'model-response.txt').write_text(raw, encoding='utf-8')
    with urlopen('http://127.0.0.1:11434/api/tags', timeout=10) as response_tags:
        tags = json.load(response_tags)
    tag = next((m for m in tags['models'] if m['name'] == args.model), {})
    metadata = {
        'model': args.model, 'digest': tag.get('digest'), 'model_details': tag.get('details'),
        'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'local Ollama /api/generate; one run; no tuning or retries',
        'options': payload['options'],
        'prompt_sha256': hashlib.sha256(payload['prompt'].encode()).hexdigest(),
        'total_duration_seconds': response.get('total_duration', 0) / 1e9,
        'done_reason': response.get('done_reason'),
        'prompt_tokens': response.get('prompt_eval_count'), 'response_tokens': response.get('eval_count'),
        'gold_in_model_input': False,
    }
    (args.case / 'model-metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    parse_error = None
    try:
        predicted = json.loads(raw)
        if not isinstance(predicted, dict):
            raise ValueError('Expected JSON object')
    except (ValueError, TypeError) as error:
        predicted = {}
        parse_error = str(error)
    (args.case / 'extracted.json').write_text(json.dumps(predicted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    gold = json.loads((args.case / 'gold.json').read_text(encoding='utf-8'))
    result = evaluate(predicted, gold)
    result['parse_error'] = parse_error
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'extraction-evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'metadata': metadata, 'evaluation': result}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

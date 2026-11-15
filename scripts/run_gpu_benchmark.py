"""Run a frozen source-only payload on one GPU; gold is never uploaded."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--gpu', required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU required')
    torch.manual_seed(42)
    jobs = json.loads(args.inputs.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    environment = {
        'model': args.model, 'revision': args.revision,
        'gpu_name': torch.cuda.get_device_name(0), 'physical_gpu_index': args.gpu,
        'gpu_total_memory_bytes': torch.cuda.get_device_properties(0).total_memory,
        'versions': {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'accelerate', 'bitsandbytes')},
        'quantization': '4-bit NF4, double quantization, FP16 compute',
        'generation': {'do_sample': False, 'max_new_tokens': 2500, 'seed': 42},
        'started_utc': datetime.now(timezone.utc).isoformat(),
    }
    (args.output / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision, cache_dir=args.cache, local_files_only=True, token=False)
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(args.model, revision=args.revision, cache_dir=args.cache, local_files_only=True, token=False,
                                              quantization_config=quantization, device_map={'': 0}, dtype=torch.float16, attn_implementation='sdpa')
    model.eval()
    for job in jobs:
        target = args.output / f'{job["case_id"]}.json'
        if target.exists():
            print('Preserving existing first response:', job['case_id'], flush=True)
            continue
        if hashlib.sha256(job['prompt'].encode()).hexdigest() != job['input_sha256']:
            raise ValueError('Input hash mismatch')
        record = {key: job[key] for key in ('case_id', 'business', 'variant', 'input_sha256')}
        record.update(model=args.model, revision=args.revision, started_utc=datetime.now(timezone.utc).isoformat())
        started = time.monotonic()
        try:
            messages = [{'role': 'system', 'content': 'Извлекай финансовые сведения из предоставленных документов. Ответ — ровно один JSON по схеме пользователя, без Markdown.'},
                        {'role': 'user', 'content': job['prompt']}]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer([text], return_tensors='pt').to('cuda:0')
            input_tokens = inputs['input_ids'].shape[-1]
            if input_tokens + 2500 > 8192:
                raise ValueError('Input exceeds the frozen 8192-token budget; no truncation allowed')
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            started = time.monotonic()
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=2500, do_sample=False, use_cache=True, pad_token_id=tokenizer.eos_token_id)
            torch.cuda.synchronize()
            generated = output[0, input_tokens:]
            raw = tokenizer.decode(generated, skip_special_tokens=True)
            record.update(raw_text=raw, prompt_tokens=input_tokens, generated_tokens=len(generated),
                          finish_reason='length' if len(generated) >= 2500 else 'stop',
                          peak_gpu_memory_bytes=torch.cuda.max_memory_allocated())
        except Exception as error:
            record.update(raw_text='', error=type(error).__name__ + ': ' + str(error))
        record.update(elapsed_seconds=time.monotonic()-started, finished_utc=datetime.now(timezone.utc).isoformat())
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target)
        print('Recorded', args.model, job['case_id'], record.get('generated_tokens'), record.get('error', 'ok'), flush=True)
    print('MODEL COMPLETE', args.model, flush=True)


if __name__ == '__main__':
    main()

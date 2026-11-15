# Восстановление проекта

Код, синтетические Word и Excel, эталоны, первые ответы обеих моделей и результаты расчётов сохранены в этом репозитории. Полный снимок перед очисткой отмечен тегом `backup-before-cleanup-2026-11-16` (коммит `356c735`).

## Восстановить файлы и результаты без моделей

```bash
git clone --branch build-case https://github.com/Egorich51/project-finance-ai-case.git
cd project-finance-ai-case
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/summarize_gpu_benchmark.py
```

Последняя команда оценивает сохранённые ответы без сети и GPU и восстанавливает исследование и два финансовых комплекта. Исходные Office-файлы и готовые результаты уже находятся в Git.

Чтобы открыть точный полный снимок до очистки:

```bash
git switch --detach backup-before-cleanup-2026-11-16
```

## Восстановить публичные веса для нового запуска

Мы использовали готовые модели; собственного обучения или уникальных обученных весов не было. Большие публичные веса не загружаются в Git. Их можно скачать заново по сохранённым названиям и ревизиям.

Предварительный локальный опыт:

```bash
ollama pull qwen2.5:1.5b
```

Digest этого первоначального варианта сохранён в `case/model-metadata.json`. При изменении тега в реестре новый digest нужно сверить с сохранённым; побайтовое совпадение новых ответов не гарантируется.

Для двух GPU-моделей точные revisions и версии библиотек находятся в `benchmarks/results/raw/qwen-1.5b/environment.json` и `benchmarks/results/raw/qwen-7b/environment.json`. В CUDA-окружении с Transformers, Accelerate, bitsandbytes и huggingface_hub загрузить именно эти ревизии можно так:

```python
import json
from pathlib import Path
from huggingface_hub import snapshot_download

for path in Path("benchmarks/results/raw").glob("*/environment.json"):
    metadata = json.loads(path.read_text())
    snapshot_download(
        metadata["model"],
        revision=metadata["revision"],
        cache_dir="model-cache",
        token=False,
        allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model", "*.jinja"],
    )
```

Для генерации используется `scripts/run_gpu_benchmark.py`; аргументы доступны через `--help`. Передайте зафиксированные `benchmarks/gpu-inputs.json`, модель, её revision, GPU, каталог весов и новый отдельный каталог результатов. Установка библиотек для GPU описывается версиями в environment.json; обычный `requirements.txt` нужен только для локальной работы с сохранёнными результатами.

Ссылки и токены доступа к Kaggle не сохранялись в Git. Для нового облачного запуска потребуется новая собственная сессия и её доступ.

## Автоматические проверки

Workflow `Reproduce example` отключён при остановке проекта. При необходимости его можно снова включить:

```bash
gh workflow enable check.yml --repo Egorich51/project-finance-ai-case
```

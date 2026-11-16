# Восстановление проекта

Текущие материалы трёх промышленных проектов находятся в `studies/industrial-v2/`. Исходный архив, распакованные документы, эталоны, все первые ответы моделей, Excel и Word сохранены в Git.

```bash
git clone --branch build-case https://github.com/Egorich51/project-finance-ai-case.git
cd project-finance-ai-case
python -m pip install -r requirements.txt
python scripts/summarize_industrial_study.py
python scripts/build_industrial_outputs.py
```

Модели заново скачивать для этих команд не нужно. Финансовый генератор создаёт Excel с формулами; для получения вычисленных кэшей откройте их в Excel/LibreOffice. Проверка независимым движком:

```bash
python scripts/verify_industrial_excel.py --soffice /path/to/soffice
```

Для нового инференса на GPU используйте отдельную папку результатов, сохранив первый запуск. Пример для 7B:

```bash
python scripts/run_gpu_benchmark.py \
  --model Qwen/Qwen2.5-7B-Instruct \
  --revision a09a35458c702b33eeacc393d103063234e8bc28 \
  --gpu 0 --inputs studies/industrial-v2/gpu-inputs.json \
  --cache /path/to/hf-cache --output /path/to/new-results \
  --max-new-tokens 3000 --context-tokens 12288
```

Для 1.5B: `Qwen/Qwen2.5-1.5B-Instruct`, ревизия `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. Библиотеки и параметры исходного запуска находятся в `results/raw/*/environment.json`, подробный протокол — в `studies/industrial-v2/PROTOCOL.md`. Публичные веса не хранятся в Git; собственного обучения не было.

Полный старый снимок перед предыдущей очисткой отмечен тегом `backup-before-cleanup-2026-11-16` (коммит `356c735`). Предыдущий парный тест можно пересчитать командой `python scripts/summarize_gpu_benchmark.py`.

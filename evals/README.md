# Evals

This folder contains evaluation scripts and datasets for reliability checks.

## Structure
```
evals/
├── data/
│   ├── brd_001.md
│   └── brd_001_expected.json
├── eval_parser.py
├── eval_schema.py
└── eval_latency.py
```

## Run
```
python evals/eval_parser.py
python evals/eval_parser_batch.py
python evals/eval_schema.py
python evals/eval_latency.py
```

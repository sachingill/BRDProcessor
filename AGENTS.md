# AGENTS

## Setup
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your OpenAI key
```

## Run (CLI)
```
python src/cli.py --input ../BRD-2-SystemGenerator/brd_agent_em/sample_inputs/sample_brd.md
```

## Run (Streamlit UI)
```
streamlit run src/ui.py
```

## E2E Validation (CLI)
```
python evals/validate_e2e.py
python evals/validate_e2e.py --cycles 10 --sleep-seconds 0.5
```

## Evals
```
python evals/eval_parser.py
python evals/eval_parser_batch.py
python evals/eval_schema.py
python evals/eval_latency.py
```

## MCP
```
python scripts/mcp_server.py
```

TODO: README references `scripts/mcp_server.py`, but `scripts/` is missing in this repo.

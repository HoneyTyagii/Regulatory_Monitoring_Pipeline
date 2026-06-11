# Regulatory Monitoring Pipeline

A multi-agent system that monitors regulatory changes across jurisdictions
(RBI, SEBI, FDA, EU AI Act, and more), determines business impact, assigns
risk, and generates actionable follow-ups for the right teams.

> Status: early development. This commit establishes project scaffolding and
> tooling. Functionality lands incrementally over subsequent commits.

## Why

Compliance teams cannot manually track every circular, guideline, and rule
change across regulators. This pipeline automates the tedious parts -
collection, cleaning, deduplication, summarization - and augments human
judgment for the parts that matter: impact analysis, risk assessment, and
action planning, always with a human-in-the-loop approval gate.

## Architecture (target)

```
Crawler Agent
    -> Document Parser
        -> Classification Agent
            -> RAG Search
                -> Risk Assessment Agent
                    -> Action Planner
                        -> Notification Agent
```

Cross-cutting concerns: long-term memory, scheduling, human approval, and an
append-only audit log.

## Project layout

```
regulatory_monitoring_pipeline/
├── src/regmon/            # application package (src layout)
│   ├── __init__.py
│   └── logging_config.py  # structured logging setup
├── tests/                 # test suite
├── pyproject.toml         # build config, dependencies, tooling
├── requirements.txt       # runtime deps
├── requirements-dev.txt   # dev/test deps
├── .env.example           # configuration template
├── .pre-commit-config.yaml
├── Makefile
└── README.md
```

## Quickstart

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
. .venv/Scripts/activate        # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install (with dev tooling)
pip install -e ".[dev]"

# 3. Configure
cp .env.example .env

# 4. Install git hooks
pre-commit install

# 5. Run checks
make lint
make test
```

## Make targets

| Target        | Description                              |
| ------------- | ---------------------------------------- |
| `make install`| Install package with dev dependencies    |
| `make lint`   | Run ruff + black (check) + mypy          |
| `make format` | Auto-format with black + ruff --fix      |
| `make test`   | Run the test suite                       |
| `make hooks`  | Install pre-commit hooks                 |
| `make clean`  | Remove caches and build artifacts        |

## Configuration

All settings are read from environment variables (see `.env.example`). The
pipeline ships with `mock` LLM and embedding providers so it runs fully
offline by default, and a `REGMON_DRY_RUN` flag that disables outbound
notifications during development.

## Roadmap

This project is built across 20 incremental commits, from scaffolding through
ingestion, storage/RAG, the agent layer, orchestration, and hardening. See the
commit history for the full progression.

## License

MIT

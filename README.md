# Regulatory Monitoring Pipeline

A multi-agent system that monitors regulatory changes across jurisdictions
(RBI, SEBI, FDA, EU AI Act), determines business impact, assigns risk, and
generates actionable follow-ups for the right teams — always with a
human-in-the-loop approval gate.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Pipeline Orchestrator                        │
│                                                                     │
│  ┌──────────┐   ┌────────┐   ┌───────────┐   ┌──────────────────┐ │
│  │ Crawler  │──>│ Parser │──>│ Normalizer│──>│ Deduplication    │ │
│  │ Agent    │   │ Agent  │   │           │   │ Engine           │ │
│  └──────────┘   └────────┘   └───────────┘   └────────┬─────────┘ │
│       │                                                │           │
│       │ (adapters: RBI, SEBI, FDA, EU)     unique docs │           │
│       │                                                ▼           │
│  ┌──────────┐   ┌────────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ Notifier │<──│ Approval   │<──│ Action   │<──│ Risk         │ │
│  │ Agent    │   │ Gate (HITL)│   │ Planner  │   │ Assessment   │ │
│  └──────────┘   └────────────┘   └──────────┘   └──────┬───────┘ │
│       │                                                  │         │
│       │ (Slack, Email)                                   │         │
│       │                                   ┌──────────────┴───────┐ │
│       │                                   │ Classification Agent │ │
│       │                                   │ + Summarization      │ │
│       │                                   │ + RAG Indexing        │ │
│       │                                   └──────────────────────┘ │
│       │                                                            │
│  ┌────┴────────────────────────────────────────────────────────┐   │
│  │              Cross-cutting: SQLite/Postgres DB               │   │
│  │  Document Store │ Audit Log │ Pipeline Memory │ Approvals   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Supported Jurisdictions

| Jurisdiction | Regulator | Sources |
|-------------|-----------|---------|
| RBI | Reserve Bank of India | Notifications, Press Releases |
| SEBI | Securities and Exchange Board of India | Legal Circulars |
| FDA | U.S. Food and Drug Administration | Press RSS, Federal Register |
| EU AI Act | European Commission | AI Act Newsroom |

## Features

- **Async crawler** with per-host rate limiting, robots.txt respect, retry/backoff
- **Source adapters** per regulator (HTML listing + RSS/Atom feed parsing)
- **Document parser** supporting HTML and PDF (via `pypdf`)
- **Content normalization** — encoding repair, boilerplate stripping, language detection
- **Deduplication** — exact (SHA-256) + near-duplicate (SimHash) across crawl runs
- **Embeddings + vector search** — chunking, mock/OpenAI embeddings, in-memory/FAISS/Chroma stores
- **RAG search service** with citations, jurisdiction filtering, score thresholding
- **Classification agent** — rule-based topic/function/urgency tagging
- **Summarization** — structured LLM summaries (mock offline + OpenAI)
- **Risk assessment** — weighted scoring (urgency, keywords, scope, penalties) + RAG context
- **Action planner** — generates owner-assigned, deadline-driven follow-up items
- **Human-in-the-loop approval** — risk-threshold gate with persisted decisions
- **Notifications** — Slack webhook + SMTP email with digest formatting and alert dedup
- **Pipeline orchestrator** — full graph wiring with persistent run memory
- **Scheduler + CLI** — `regmon run|backfill|status|sources` commands
- **Append-only audit log** across all pipeline events

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
. .venv/Scripts/activate        # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install with dev tooling
pip install -e ".[dev]"

# 3. Configure
cp .env.example .env

# 4. Run checks
make lint
make test

# 5. Run the pipeline
regmon sources                  # list configured sources
regmon run                      # one-shot pipeline run
regmon run --loop --interval 60 # continuous mode
regmon status                   # check pipeline state
regmon backfill                 # re-process ignoring dedup
```

## Project Layout

```
src/regmon/
├── __init__.py, __main__.py, cli.py, scheduler.py
├── config/          # Settings, secrets, source registry
├── models/          # Pydantic domain models and enums
├── crawler/         # Async fetcher, rate limiter, robots.txt, adapters
├── parser/          # HTML/PDF extraction, metadata (dates, ref numbers)
├── normalize/       # Encoding repair, boilerplate strip, language detect
├── dedup/           # Content hashing, SimHash near-duplicate engine
├── embeddings/      # Chunking, providers, vector stores, indexer
├── rag/             # Semantic search service with citations
├── classification/  # Rule-based + LLM topic/function classifier
├── summarization/   # Structured LLM summaries (mock + OpenAI)
├── risk/            # Risk scoring, rationale, assessment agent
├── actions/         # Action planner with templates and due dates
├── approval/        # Human-in-the-loop gate with persisted decisions
├── notifications/   # Slack/email channels, digest formatting, dedup
├── pipeline/        # Orchestrator, state tracking, run context
└── db/              # SQLAlchemy engine, document store, audit log
tests/               # Unit + integration test suite
.github/workflows/   # CI pipeline (lint, test matrix, integration)
```

## Configuration

All settings are read from environment variables (see `.env.example`). The
pipeline ships with `mock` LLM and embedding providers so it runs fully
offline by default. Set `REGMON_DRY_RUN=true` to suppress outbound notifications.

### Optional Extras

```bash
pip install -e ".[faiss]"    # FAISS vector store backend
pip install -e ".[chroma]"   # Chroma vector store backend
pip install -e ".[openai]"   # OpenAI embeddings + LLM
```

## Testing

```bash
make test                    # unit tests
pytest -m integration        # integration tests
pytest --cov=regmon          # with coverage
```

The test suite uses in-memory SQLite and `httpx.MockTransport` so no external
services are needed. Integration tests are marked with `@pytest.mark.integration`.

## Make Targets

| Target | Description |
|--------|-------------|
| `make install` | Install package with dev dependencies |
| `make lint` | Run ruff + black (check) + mypy |
| `make format` | Auto-format with black + ruff --fix |
| `make test` | Run the test suite |
| `make test-cov` | Run tests with coverage report |
| `make hooks` | Install pre-commit hooks |
| `make clean` | Remove caches and build artifacts |

## License

MIT

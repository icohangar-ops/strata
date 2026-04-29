# Strata

> **Maturity-assessed, rubric-graded AI operating system for the CFO / VP Finance function.**
> Two-axis maturity assessment + 12 chain-driven deliverables, all underpinned by one
> hierarchical rubric schema. Handbook-aligned, LLM-agnostic, deploy-ready.

[![Test](https://github.com/zan-maker/strata/actions/workflows/test.yml/badge.svg)](https://github.com/zan-maker/strata/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)](#tests)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/downloads/release/python-3120/)
[![License Proprietary](https://img.shields.io/badge/license-Proprietary-lightgrey)](#license)

---

## Demo

https://github.com/zan-maker/strata/releases/download/v0.7.0/demo.mp4

> _3-minute walkthrough: title & architecture, dual-axis CLI maturity assessment, visual heatmaps, 90-day phased roadmap, deliverable chain execution pipeline, 12 deliverables overview, and tech stack._

### Screenshots

| Screenshot | What it shows |
|---|---|
| ![Assess tab](docs/screenshots/01-assess.png) | **Assess** tab — dual-axis heatmap (function + competency) with KPI summary cards |
| ![Roadmap tab](docs/screenshots/02-roadmap.png) | **Roadmap** tab — 90-day phased plan (Baseline, Scale, Embed) with capability scores |
| ![Deliver tab](docs/screenshots/03-deliver.png) | **Deliver** tab — chain selector + 5-stage execution pipeline + score history |
| ![12 Deliverables](docs/screenshots/04-deliverables.png) | **12 chain-driven deliverables** covering board, BvA, M&A, investor, 3-statement, risk, and more |
| ![Tech Stack](docs/screenshots/05-techstack.png) | **Tech stack** — Python 3.12, Streamlit, PostgreSQL, Pydantic, pluggable LLM backends |

---

## What is Strata?

Strata is an opinionated decomposition of the modern CFO function into **two scoring
axes** (process maturity + competency archetype) and **twelve chain-driven
deliverables** (board pack, BvA commentary, IC memo, investor update, 3-statement
model, CFO dashboard, risk register, capex memo, post-investment review, employee
all-hands, cross-functional brief, earnings script). Every assessment, every
deliverable, and every grading run shares a single hierarchical rubric schema —
so the same engine that scores "how mature is your monthly close" also scores
"how good is this draft of the board pack."

It's an opinionated implementation of the modern strategic-CFO function:
the operational scorecard, the competency archetype, the standing
deliverables, and the 90-day rollout plan — wired together as a single
clean-room codebase shipping with Postgres schema, Streamlit UI, and
Railway deployment.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  L0  USER SHELL                  (CLI · Streamlit UI)             │
├───────────────────────────────────────────────────────────────────┤
│  L1  MATURITY ASSESSMENT                                          │
│      Function axis      : 8 process capabilities                  │
│      Competency axis    : 5 strategic-CFO pillars                 │
│      90-day Roadmap     : phased plan keyed off the heatmap       │
├───────────────────────────────────────────────────────────────────┤
│  L2  CAPABILITY CATALOG                                           │
│      22 skills bucketed across ingest / record / analyze / plan / │
│      present phases; each skill ties to a capability and may      │
│      drive a deliverable rubric                                   │
├───────────────────────────────────────────────────────────────────┤
│  L3  DIRECTOR                                                     │
│      decide(assessment) → RouteDecision                           │
│      route(assessment, inputs) → executes weakest-cap chain       │
│      chain composition (depends_on), perception adapters,         │
│      LLM-backend switch (DashScope/Qwen by default, Anthropic     │
│      optional)                                                    │
├───────────────────────────────────────────────────────────────────┤
│  L4  DELIVERABLE FACTORY                                          │
│      persona → draft → grader → revise loop → pass-or-max-iter    │
│      12 chains, each with a chain_id, rubric, persona, mock       │
│      author + (optional) LLM author                               │
├───────────────────────────────────────────────────────────────────┤
│  L5  CANONICAL RUBRIC SCHEMA                                      │
│      Group → Characteristic → Attribute, weight-bounded, sum-     │
│      to-one validated. One Pydantic model serves both L1 and L4.  │
│      Per-tenant rubric_override stored in Postgres.               │
└───────────────────────────────────────────────────────────────────┘
```

---

## What's inside

### L1 — 8 function-axis capabilities

| Capability | Rubric ID |
|---|---|
| Monthly Close | `rb.function.close` |
| Account Reconciliation | `rb.function.reconcile` |
| Board Pack Production | `rb.function.board_pack` |
| Budget vs Actual Analysis | `rb.function.bva` |
| Forecasting | `rb.function.forecast` |
| M&A Diligence and IC Discipline | `rb.function.ma` |
| Enterprise Risk Management | `rb.function.risk` |
| Capital Allocation Discipline | `rb.function.capital_allocation` |

### L1 — 5 competency-axis pillars (strategic-CFO archetype)

| Pillar | Rubric ID |
|---|---|
| Strategic Financial Leadership | `rb.competency.strategic_leadership` |
| Advanced FP&A and Decision-Making | `rb.competency.fpna` |
| Digital Transformation and Technology | `rb.competency.digital` |
| Stakeholder Management and Communication | `rb.competency.stakeholder` |
| Risk Management and Governance | `rb.competency.risk_governance` |

### L4 — 12 chain-driven deliverables

| Chain | Deliverable rubric | What it produces |
|---|---|---|
| `chain.board_pack.v1` | `rb.deliverable.board_pack` | Monthly board pack |
| `chain.bva_commentary.v1` | `rb.deliverable.bva_commentary` | Variance commentary (with GL CSV perception) |
| `chain.ma_memo.v1` | `rb.deliverable.ma_memo` | Investment-committee acquisition memo |
| `chain.investor_update.v1` | `rb.deliverable.investor_update` | Quarterly investor letter |
| `chain.three_statement.v1` | `rb.deliverable.three_statement` | Integrated 3-statement model spec |
| `chain.cfo_dashboard.v1` | `rb.deliverable.cfo_dashboard` | One-page value-creation dashboard |
| `chain.risk_register.v1` | `rb.deliverable.risk_register` | Enterprise risk register |
| `chain.capex_memo.v1` | `rb.deliverable.capex_memo` | Capital council capex memo |
| `chain.post_investment_review.v1` | `rb.deliverable.post_investment_review` | 12/24-month look-back |
| `chain.employee_all_hands.v1` | `rb.deliverable.employee_all_hands` | All-hands finance segment |
| `chain.cross_functional_brief.v1` | `rb.deliverable.cross_functional_brief` | Bi-weekly peer-function brief |
| `chain.earnings_script.v1` | `rb.deliverable.earnings_script` | Earnings call script + Q&A prep |

### CFO function coverage

| Strategic CFO surface | Strata coverage |
|---|---|
| 5-pillar competency scorecard (5×4 cells) | ✅ 20/20 cells |
| One-page value-creation dashboard | ✅ chain + rubric |
| Communication playbook across 5 venues | ✅ board, investor letter, employee, cross-functional, earnings |
| Enterprise risk management framework | ✅ capability + risk-register deliverable |
| Capital-allocation discipline (4-stage gate) | ✅ capability + capex memo + post-investment review |
| 90-day phased rollout roadmap | ✅ `plan_90_days` API + CLI + Streamlit tab |

---

## Quick start — local

```bash
# 1) Clone
git clone https://github.com/zan-maker/strata.git
cd strata

# 2) Virtualenv + install (Windows bash; on macOS/Linux use .venv/bin/activate)
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev,llm,ui]"

# 3) Configure env (copy then edit; never commit your real .env)
cp .env.example .env

# 4) Postgres + migrations (skip if you only use SQLite for tests)
docker compose up -d postgres
alembic upgrade head

# 5) Try the CLI — no API key needed (mock author/grader)
strata assess --self-assessment samples/maturity_self_assessment.yaml --axis both
strata roadmap --self-assessment samples/maturity_self_assessment.yaml
strata board-pack --inputs samples/board_pack_inputs.json

# 6) Or launch the Streamlit UI
streamlit run streamlit_app.py
```

## Quick start — Railway (deployed)

The repo ships with a [`Dockerfile`](./Dockerfile), [`railway.toml`](./railway.toml),
and a [`.streamlit/config.toml`](./.streamlit/config.toml) tuned for headless
production.

1. In the Railway dashboard: **+ New** → **Deploy from GitHub repo** → select this repo.
2. **+ New** → **Database** → **PostgreSQL** (auto-injects `DATABASE_URL`).
3. Service → **Variables** → set the env vars in [`.env.example`](./.env.example).
4. Service → **Settings** → **Networking** → **Generate Domain**.

Every push to `main` auto-redeploys via Railway's native GitHub integration.

---

## Configuration

Environment variables (full list in [`.env.example`](./.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://strata:strata@localhost:5433/strata` | Postgres connection (Railway injects automatically) |
| `STRATA_LLM_BACKEND` | `openai` | `openai` (DashScope/OpenAI-compatible) or `anthropic` |
| `STRATA_LLM_BASE_URL` | DashScope China endpoint | OpenAI-compatible base URL |
| `DASHSCOPE_API_KEY` | _unset_ | Active when `backend=openai` |
| `ANTHROPIC_API_KEY` | _unset_ | Active when `backend=anthropic` |
| `STRATA_GRADER_MODEL` | `qwen3.6-flash` | Model used by the rubric grader |
| `STRATA_AUTHOR_MODEL` | `qwen3.6-flash` | Model used by the author |
| `STRATA_MAX_ITERATIONS` | `5` | Cap on revise-and-grade loops |
| `STRATA_PASS_THRESHOLD` | `8` | Score threshold (out of rubric max) for pass |
| `ASTRA_DB_API_ENDPOINT` | _unset_ | Astra DB API URL (vector exemplar store; optional) |
| `ASTRA_DB_APPLICATION_TOKEN` | _unset_ | Astra DB token |
| `ASTRA_DB_KEYSPACE` | `default_keyspace` | Astra keyspace |
| `STRATA_EXEMPLAR_TOP_K` | `3` | Past drafts to inject into the author prompt |

Verified models on DashScope (lowercase): `qwen3.6-flash`, `qwen3.6-35b-a3b`,
`qwen3.6-plus`, `qwen3.5-plus`. Use `qwen3.6-flash` for speed/cost.

### Vector exemplar store (v0.7.0)

When `ASTRA_DB_API_ENDPOINT` and `ASTRA_DB_APPLICATION_TOKEN` are set, the
deliverable factory queries Astra DB for the top-K most similar prior drafts
of the same chain and splices them into the author prompt as exemplars. After
each successful run with `normalized_pct >= 80%`, the draft is auto-ingested
into the store so the corpus grows organically. **Postgres remains the
relational core** — Astra is purely additive.

```bash
# Manually ingest a known-good draft as a seed exemplar
strata exemplars ingest chain.bva_commentary.v1 prior_draft.md \
  --target-id "acme::feb_2026" --score-pct 88

# Search for similar past drafts
strata exemplars search chain.bva_commentary.v1 \
  --query "March 2026 hardware revenue miss volume mix"

# How many exemplars do I have?
strata exemplars count
strata exemplars count --chain-id chain.bva_commentary.v1
```

---

## CLI

```bash
strata --help                                 # top-level help
strata rubrics                                # list every loaded rubric
strata chains                                 # list every registered chain
strata assess     --self-assessment FILE      # L1 maturity heatmap (--axis function|competency|both)
strata roadmap    --self-assessment FILE      # 90-day phased plan
strata run        --self-assessment FILE \    # dynamic routing: weakest-cap chain wins
                  --inputs FILE [--use-llm]
strata board-pack --inputs FILE [--use-llm]   # always-board-pack convenience entrypoint
```

The `--use-llm` flag swaps the mock author + grader for the configured LLM backend.

---

## Streamlit UI

`streamlit run streamlit_app.py` opens a three-tab UI:

- **Assess** — dual-axis heatmap with weak/developing/mature verdicts
- **Roadmap** — phased 90-day plan with chain pointers
- **Deliver** — chain selector, JSON inputs editor, optional GL CSV uploader for
  perception-aware chains, draft renderer, score history, Markdown download

Sidebar shows live backend status (which key is set, which model, which base URL).

---

## Tests

```bash
pytest                                                # 155 tests (the suite ships green)
pytest --cov                                          # 97% coverage
ANTHROPIC_API_KEY=sk-... pytest -m live_llm          # opt-in live test against any of 12 chains
DASHSCOPE_API_KEY=sk-... STRATA_LLM_BACKEND=openai \
  pytest -m live_llm                                  # same, via DashScope/Qwen
STRATA_LIVE_POSTGRES_URL=postgresql+psycopg://... \
  pytest -m live_postgres                             # opt-in live Postgres alembic verification
```

The non-`live_*` suite runs entirely offline — no API keys, no Docker. Tests:

| | |
|---|---|
| Pydantic schema invariants | weight bounds, sum-to-one, attribute-score uniqueness |
| Rubric YAML loading | every shipped rubric parses and round-trips |
| Maturity assessor | floor/ceiling/baseline scoring, missing-score errors |
| Deliverable factory | iteration loop, pass/fail thresholds, history capture |
| Director routing | weakest-cap selection, alphabetical tiebreaker, `preferred_deliverable` override |
| Chain composition | dependency execution, cycle detection |
| Tenant overrides | weight renormalization, score clamping, characteristic disable |
| Perception adapters | GL CSV aggregation, identity passthrough |
| Alembic migrations | linear chain, ORM-table parity, round-trip on SQLite |
| CLI | every subcommand + axis flag + error paths |

---

## Project structure

```
strata/
├── src/strata/
│   ├── schema.py              # L5: Pydantic rubric model
│   ├── registry.py            # YAML rubric loader
│   ├── models.py              # SQLAlchemy: rubric, rubric_score, run_log, rubric_override
│   ├── config.py              # env-driven Settings
│   ├── db.py                  # SQLAlchemy engine + session_scope
│   ├── cli.py                 # Typer CLI entrypoints
│   ├── rubrics/
│   │   ├── deliverable/       # 12 deliverable rubrics
│   │   ├── function/          # 8 function-axis capability rubrics
│   │   └── competency/        # 5 competency-axis pillar rubrics
│   ├── catalog/               # L2 skill catalog (YAML + loader)
│   ├── deliverable/           # L4 factory, grader, author, persona, 12 mock authors
│   ├── maturity/              # L1 assessor, competency assessor, roadmap, overrides
│   ├── orchestrator/          # L3 Director, chain registry, decide/route logic
│   └── perception/            # Source-system adapters (CSV GL today)
├── migrations/                # Alembic migrations
├── samples/                   # 12 input JSONs + GL extract CSV + self-assessment YAML
├── tests/                     # 155 tests
├── streamlit_app.py
├── Dockerfile
├── railway.toml
├── docker-compose.yml         # local Postgres
├── .github/workflows/         # test.yml + deploy.yml
└── NOTICE                     # upstream attribution
```

---

## License

Proprietary. See [NOTICE](./NOTICE) for upstream attribution and clean-room
boundaries with respect to the open-source projects whose patterns inspired
parts of Strata's architecture (FinOps Foundation, CFO Stack, Awesome Notebooks,
Open Risk, FinRobot, FP&A AI Agent).

---

## References

See [NOTICE](./NOTICE) for the full upstream-inspiration list.

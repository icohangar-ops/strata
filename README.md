# Strata

Maturity-assessed, rubric-graded AI copilot for the CFO / VP Finance function.

Five layers, one schema:

| Layer | Purpose |
|---|---|
| L1 — Maturity | Score the finance function across capabilities × lenses |
| L2 — Catalog  | Capability and skill registry |
| L3 — Director | Routes a job to a skill chain |
| L4 — Deliverable Factory | Persona-prompted draft, rubric-graded, iterated to threshold |
| L5 — Rubric Schema | Hierarchical Group → Characteristic → Attribute store underpinning L1 and L4 |

Attribution for upstream architectural inspirations: see [NOTICE](./NOTICE).

## Quick start

```bash
python -m venv .venv
source .venv/Scripts/activate     # Windows bash
pip install -e ".[dev]"

cp .env.example .env
docker compose up -d postgres
alembic upgrade head

# Run the board-pack vertical slice (uses mock grader; no API key required)
strata board-pack --inputs samples/board_pack_inputs.json
```

## Tests

```bash
pytest
```

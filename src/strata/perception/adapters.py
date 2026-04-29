"""Perception adapters — pluggable source-system pulls.

A perception adapter is `Callable[[dict], dict]` that enriches the inputs dict
*before* the deliverable factory authors a draft. v3 ships:

  * identity_adapter      — passthrough (default for chains with no perception set)
  * csv_gl_adapter        — reads a general-ledger CSV extract, computes a few
                            common aggregates (period revenue, opex, headline
                            variances), and merges them into inputs

Production v4 would add ERP-specific pullers (NetSuite, QuickBooks, Sage Intacct)
behind the same protocol. The CSV adapter exists so chains have something real
to consume in offline tests and demos.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

PerceptionAdapter = Callable[[dict[str, Any]], dict[str, Any]]


def identity_adapter(inputs: dict[str, Any]) -> dict[str, Any]:
    return inputs


def csv_gl_adapter(
    csv_path_key: str = "gl_extract_path",
    *,
    period_key: str = "period",
    out_key: str = "gl_aggregates",
) -> PerceptionAdapter:
    """Builds an adapter that reads a GL extract CSV and merges aggregates into inputs.

    The CSV must have columns: period, account, account_type, amount.
    `account_type` ∈ {revenue, cogs, opex, asset, liability, equity}.

    The adapter writes `inputs[out_key]` = {
        "period": ...,
        "revenue": float, "cogs": float, "opex": float,
        "gross_margin_pct": float | None,
        "by_account": {account: amount, ...},
    }

    If `csv_path_key` is missing from inputs, returns inputs unchanged (chain
    just runs without GL enrichment).
    """

    def _adapter(inputs: dict[str, Any]) -> dict[str, Any]:
        path = inputs.get(csv_path_key)
        if not path:
            return inputs
        period = inputs.get(period_key)
        agg = _aggregate(Path(path), filter_period=period)
        if not agg:
            return inputs
        out = dict(inputs)
        out[out_key] = agg
        return out

    return _adapter


def _aggregate(path: Path, filter_period: str | None) -> dict[str, Any]:
    by_type: dict[str, float] = defaultdict(float)
    by_account: dict[str, float] = defaultdict(float)
    period_seen: str | None = None
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if filter_period and row["period"] != filter_period:
                continue
            period_seen = period_seen or row["period"]
            amount = float(row["amount"])
            by_type[row["account_type"]] += amount
            by_account[row["account"]] += amount
    if not period_seen:
        return {}
    revenue = by_type.get("revenue", 0.0)
    cogs = by_type.get("cogs", 0.0)
    opex = by_type.get("opex", 0.0)
    gm_pct = ((revenue - cogs) / revenue * 100.0) if revenue else None
    return {
        "period": period_seen,
        "revenue": revenue,
        "cogs": cogs,
        "opex": opex,
        "gross_margin_pct": gm_pct,
        "by_account": dict(by_account),
    }

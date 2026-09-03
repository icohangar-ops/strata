"""Minimal stdio MCP server for Strata."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable

from strata import registry
from strata.maturity import (
    CAPABILITY_RUBRIC_IDS,
    COMPETENCY_RUBRIC_IDS,
    CompetencyAssessor,
    MaturityAssessor,
)
from strata.maturity.roadmap import plan_90_days
from strata.schema import CharacteristicScore


JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None
ToolHandler = Callable[[dict[str, Any]], JsonValue]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class StdioServer:
    def __init__(self, name: str, version: str, tools: list[ToolSpec]) -> None:
        self.name = name
        self.version = version
        self.tools = {tool.name: tool for tool in tools}

    def serve(self) -> None:
        while True:
            message = _read_message()
            if message is None:
                return
            method = message.get("method")
            if method == "initialize":
                _respond(
                    message,
                    {
                        "protocolVersion": message.get("params", {}).get(
                            "protocolVersion", "2024-11-05"
                        ),
                        "serverInfo": {"name": self.name, "version": self.version},
                        "capabilities": {"tools": {"listChanged": False}},
                    },
                )
                continue
            if method == "tools/list":
                _respond(
                    message,
                    {"tools": [self._tool_entry(tool) for tool in self.tools.values()]},
                )
                continue
            if method == "tools/call":
                self._call_tool(message)
                continue
            if method in {"shutdown", "exit"}:
                if message.get("id") is not None:
                    _respond(message, {})
                return

    def _tool_entry(self, tool: ToolSpec) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }

    def _call_tool(self, message: dict[str, Any]) -> None:
        params = message.get("params", {})
        tool = self.tools.get(params.get("name"))
        if tool is None:
            _error(message, -32602, f"unknown tool: {params.get('name')}")
            return
        try:
            result = tool.handler(params.get("arguments") or {})
        except Exception as exc:  # pragma: no cover - surfaced to caller
            _error(message, -32000, str(exc))
            return
        _respond(
            message,
            {
                "content": [
                    {"type": "text", "text": json.dumps(result, indent=2, default=str)}
                ]
            },
        )


def serve() -> None:
    server = StdioServer(
        name="strata",
        version="0.7.0",
        tools=[
            ToolSpec(
                name="assess",
                description="Run the maturity assessor on inline rubric scores.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_id": {"type": "string"},
                        "axis": {"type": "string", "enum": ["function", "competency"]},
                        "self_assessment": {"type": "object"},
                    },
                    "required": ["target_id", "self_assessment"],
                },
                handler=_assess_tool,
            ),
            ToolSpec(
                name="roadmap",
                description="Generate a 90-day roadmap from inline rubric scores.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_id": {"type": "string"},
                        "axis": {"type": "string", "enum": ["function", "competency"]},
                        "self_assessment": {"type": "object"},
                    },
                    "required": ["target_id", "self_assessment"],
                },
                handler=_roadmap_tool,
            ),
            ToolSpec(
                name="list_rubrics",
                description="List the loaded rubrics and their scopes.",
                input_schema={"type": "object", "properties": {}},
                handler=lambda _args: _list_rubrics(),
            ),
        ],
    )
    server.serve()


def _assess_tool(args: dict[str, Any]) -> dict[str, Any]:
    axis = args.get("axis", "function")
    target_id = args["target_id"]
    scores = _scores_from_payload(args["self_assessment"], axis)
    if axis == "competency":
        result = CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=scores)
    else:
        result = MaturityAssessor().assess(target_id=target_id, scores_by_rubric=scores)
    return {
        "target_id": result.target_id,
        "axis": axis,
        "overall_pct": result.overall_pct,
        "heatmap": [{"capability": name, "score_pct": pct} for name, pct in result.heatmap()],
    }


def _roadmap_tool(args: dict[str, Any]) -> dict[str, Any]:
    axis = args.get("axis", "function")
    target_id = args["target_id"]
    scores = _scores_from_payload(args["self_assessment"], axis)
    if axis == "competency":
        assessment = CompetencyAssessor().assess(target_id=target_id, scores_by_rubric=scores)
    else:
        assessment = MaturityAssessor().assess(target_id=target_id, scores_by_rubric=scores)
    roadmap = plan_90_days(assessment, axis=axis)
    return {
        "target_id": roadmap.target_id,
        "axis": roadmap.axis,
        "overall_pct": roadmap.overall_pct,
        "phases": [
            {
                "label": phase.label,
                "intent": phase.intent,
                "actions": [
                    {
                        "capability_name": action.capability_name,
                        "score_pct": action.score_pct,
                        "action": action.action,
                        "chain_id": action.chain_id,
                        "deliverable_rubric_id": action.deliverable_rubric_id,
                    }
                    for action in phase.actions
                ],
            }
            for phase in roadmap.phases
        ],
    }


def _list_rubrics() -> dict[str, Any]:
    loaded = registry.load_all()
    return {
        "rubrics": [
            {
                "rubric_id": rb.rubric_id,
                "scope": rb.scope,
                "name": rb.name,
                "groups": len(rb.groups),
                "max_score": rb.max_score,
            }
            for rb in sorted(loaded.values(), key=lambda r: r.rubric_id)
        ]
    }


def _scores_from_payload(
    payload: dict[str, Any], axis: str
) -> dict[str, list[CharacteristicScore]]:
    rubric_ids = CAPABILITY_RUBRIC_IDS if axis == "function" else COMPETENCY_RUBRIC_IDS
    scores: dict[str, list[CharacteristicScore]] = {}
    for rid in rubric_ids:
        raw = payload.get(rid)
        if raw is None:
            raise ValueError(f"missing scores for rubric '{rid}'")
        scores[rid] = _normalize_characteristic_scores(raw)
    return scores


def _normalize_characteristic_scores(raw: Any) -> list[CharacteristicScore]:
    items: list[CharacteristicScore] = []
    if isinstance(raw, dict):
        for characteristic_id, score in raw.items():
            items.append(
                CharacteristicScore(
                    characteristic_id=str(characteristic_id),
                    score=int(score),
                    rationale="self-assessed",
                )
            )
        return items
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                raise TypeError("score items must be objects")
            items.append(
                CharacteristicScore(
                    characteristic_id=str(item["characteristic_id"]),
                    score=int(item["score"]),
                    rationale=str(item.get("rationale", "self-assessed")),
                )
            )
        return items
    raise TypeError("self_assessment entries must be objects or lists of score objects")


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        stripped = line.decode("utf-8", errors="replace").strip()
        if not stripped:
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        headers[key.lower().strip()] = value.strip()
    length = int(headers.get("content-length", "0"))
    payload = sys.stdin.buffer.read(length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def _respond(message: dict[str, Any], result: dict[str, Any]) -> None:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": message.get("id"), "result": result},
        default=str,
    ).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _error(message: dict[str, Any], code: int, detail: str) -> None:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": code, "message": detail}},
        default=str,
    ).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog="strata mcp", description="Run the Strata MCP server.")


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    serve()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

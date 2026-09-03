from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rust" / "Cargo.toml"
DEBUG_BIN = ROOT / "rust" / "target" / "debug" / "strata-core"
RELEASE_BIN = ROOT / "rust" / "target" / "release" / "strata-core"


def run_strata_core(command: str, payload: dict) -> dict:
    request = json.dumps({"command": command, "input": payload})
    if RELEASE_BIN.exists():
        proc = subprocess.run(
            [str(RELEASE_BIN)], input=request, text=True, capture_output=True, check=True
        )
        return json.loads(proc.stdout)
    if DEBUG_BIN.exists():
        proc = subprocess.run(
            [str(DEBUG_BIN)], input=request, text=True, capture_output=True, check=True
        )
        return json.loads(proc.stdout)

    proc = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(MANIFEST), "--bin", "strata-core"],
        input=request,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)

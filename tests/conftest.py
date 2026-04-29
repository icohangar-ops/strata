import os
import sys
from pathlib import Path

# Ensure src/ is importable when running pytest without `pip install -e`
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Use SQLite for tests so they run without docker / postgres.
os.environ.setdefault("STRATA_TEST_DB", "sqlite:///./strata-test.sqlite")

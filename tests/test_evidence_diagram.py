"""Only source-supported excerpts may appear in a student evidence flow."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Socratic-Chat/backend"))

from platform_app.evidence_diagram import verified_steps


SOURCE = "What would you like? small Please insert coins. Money refunded. What would you like? medium Sandwich is ready."


def test_diagram_uses_only_source_quotes_in_order():
    steps = ["What would you like? small", "Please insert coins.", "Money refunded."]
    assert verified_steps(json.dumps({"steps": steps}), SOURCE) == steps


@pytest.mark.parametrize("steps", [
    ["What would you like? small", "The machine checks bread automatically."],
    ["Money refunded.", "Please insert coins."],
    ["Money refunded."],
])
def test_diagram_rejects_invented_reordered_or_too_few_steps(steps):
    with pytest.raises(ValueError):
        verified_steps(json.dumps({"steps": steps}), SOURCE)

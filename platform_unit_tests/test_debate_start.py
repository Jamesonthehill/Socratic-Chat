from platform_app import engines


SCENARIO = "Should teams require code review before merging a change?"


def _start(opening_prompt=""):
    return engines.start(
        {"tool": "debate", "snapshot": {"config": {"scenario": SCENARIO, "opening_prompt": opening_prompt}}},
        {},
    )


def test_debate_starts_with_instructor_scenario_by_default():
    assert _start()["messages"] == [{"role": "assistant", "content": SCENARIO}]


def test_debate_keeps_custom_instructor_opening():
    assert _start("Which position would you defend?")["messages"] == [
        {"role": "assistant", "content": "Which position would you defend?"}
    ]


def test_debate_replaces_legacy_generic_canvas_opening():
    assert _start("Take a position on this scenario and explain your strongest reason.")["messages"] == [
        {"role": "assistant", "content": SCENARIO}
    ]

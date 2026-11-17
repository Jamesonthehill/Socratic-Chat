from platform_app.learning_journey import summarize_difficulty


def peer(rating):
    return {"engine_state": {"socratic": {"step_metrics": {"0": {"difficulty": rating}}}}}


def test_one_valid_classmate_rating_is_enough_for_comparison():
    steps = [{"title": "First step"}, {"title": "Second step"}]
    result = summarize_difficulty(steps, [peer("easy"), peer("skipped"), peer("invalid")])
    assert result["steps"][0]["available"]
    assert result["steps"][0]["responses"] == 1
    assert result["steps"][0]["counts"]["easy"] == 1
    assert not result["steps"][1]["available"]


def test_counts_are_per_step_with_no_student_data():
    result = summarize_difficulty([{"title": "First step"}], [peer("easy"), peer("hard"), peer("hard")])
    assert result["steps"][0]["counts"] == {"easy": 1, "somewhat_easy": 0, "moderate": 0, "somewhat_hard": 0, "hard": 2}
    assert result["steps"][0]["responses"] == 3
    assert "engine_state" not in str(result)

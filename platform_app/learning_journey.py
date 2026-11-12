"""Anonymous, self-reported step difficulty summaries."""


from typing import Literal, get_args


StepDifficulty = Literal["easy", "somewhat_easy", "moderate", "somewhat_hard", "hard", "skipped"]
RATED_DIFFICULTIES = tuple(rating for rating in get_args(StepDifficulty) if rating != "skipped")


def summarize_difficulty(steps, peers):
    result = []
    for index, step in enumerate(steps):
        counts = dict.fromkeys(RATED_DIFFICULTIES, 0)
        for peer in peers:
            metrics = ((peer.get("engine_state") or {}).get("socratic") or {}).get("step_metrics") or {}
            difficulty = (metrics.get(str(index)) or {}).get("difficulty")
            if difficulty in counts:
                counts[difficulty] += 1
        total = sum(counts.values())
        available = total > 0
        result.append({"step_index": index, "title": step["title"], "available": available,
                       "responses": total if available else None,
                       "counts": counts if available else None})
    return {"steps": result}

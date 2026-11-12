"""Anonymous, self-reported step difficulty summaries."""


def summarize_difficulty(steps, peers, minimum_responses=3):
    result = []
    for index, step in enumerate(steps):
        counts = {"easy": 0, "moderate": 0, "hard": 0}
        for peer in peers:
            metrics = ((peer.get("engine_state") or {}).get("socratic") or {}).get("step_metrics") or {}
            difficulty = (metrics.get(str(index)) or {}).get("difficulty")
            if difficulty in counts:
                counts[difficulty] += 1
        total = sum(counts.values())
        available = total >= minimum_responses
        result.append({"step_index": index, "title": step["title"], "available": available,
                       "responses": total if available else None,
                       "counts": counts if available else None})
    return {"minimum_responses": minimum_responses, "steps": result}

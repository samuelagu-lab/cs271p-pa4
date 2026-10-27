"""Public bonus practice catalog. Private grading inputs are not included."""
import json
from pathlib import Path

import problem

GROUP_POINTS = {"rooms": 4, "wall": 1}


def catalog(final=False):
    data = json.loads((Path(__file__).resolve().parent / "practice_bonus_cases.json").read_text())
    entries = data["final" if final else "regular"]
    for entry in entries:
        checked = problem.check_output(entry["instance"], entry["target_board"])
        if entry["bonus_group"] not in GROUP_POINTS or not entry["exact_optimum"] or not checked["valid"] or checked["value"] != entry["target_value"]:
            raise ValueError("invalid public bonus witness")
    return entries


def practice_score(records):
    """Score a full public practice suite; partial-case runs report no total."""
    groups = {key: [] for key in GROUP_POINTS}
    for row in records:
        groups[row["bonus_group"]].append(row["bonus_matched"])
    if any(not outcomes for outcomes in groups.values()):
        raise ValueError("both bonus groups are needed for a practice total")
    return sum(GROUP_POINTS[key] * sum(outcomes) / len(outcomes) for key, outcomes in groups.items())

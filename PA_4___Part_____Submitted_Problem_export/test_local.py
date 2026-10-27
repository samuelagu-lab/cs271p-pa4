"""Readable local feedback on representative cases with reachable witnesses."""
import argparse
import json
from pathlib import Path

import problem
import runner
import cases
import bonus_cases


def catalog(final=False):
    return cases.catalog(final)


def draw(entry, checked):
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("Optional plots need matplotlib and NumPy; text results remain available.")
        return
    c = entry["instance"]
    boards = [("Input weights", None), ("Public target witness", entry["target_board"])]
    if checked is not None and checked["valid"]:
        boards.append(("Your checked board", checked["answer"]))
    fig, axes = plt.subplots(1, len(boards), figsize=(5*len(boards), 5), squeeze=False,
                             layout="constrained")
    weights = np.asarray(c["weights"], dtype=float)
    blocked = np.asarray(c["blocked"])
    for ax, (title, board) in zip(axes[0], boards):
        shade = np.ma.array(weights, mask=blocked)
        cmap = plt.get_cmap("YlGnBu").copy()
        cmap.set_bad("#656565")
        image = ax.imshow(shade, cmap=cmap, vmin=0, vmax=float(weights.max()))
        if board is not None:
            live = np.argwhere(board)
            if len(live):
                ax.scatter(live[:,1], live[:,0], marker="s", s=65,
                           facecolors="none", edgecolors="#e54b20", linewidths=1.2)
            value = problem.check_output(c, board)["value"]
            title += f"\nvalue {value}"
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(entry["name"]+" — gray: blocked; orange squares: live")
    fig.colorbar(image, ax=list(axes[0]), label="Cell weight", fraction=.025, pad=.025)
    plt.show()
    plt.close(fig)


def run_case(entry, module, seconds, seed, draw=False, compare=True):
    c = entry["instance"]
    result = runner.run(module, c, seconds=seconds, seed=seed)
    checked = runner.checked_garden(c, result)
    print(f"{entry['name']}: {'VALID' if checked['valid'] else 'INVALID'}; "
          f"{result['termination']}; search {result['search_elapsed']:.3f}s")
    if checked["valid"]:
        print("Your value:", checked["value"])
        if entry.get("tiny_optimum"):
            print("Exact tiny optimum:",entry["target_value"],
                  "(matched)" if checked["value"]==entry["target_value"] else "(not yet matched)")
        if entry.get("bonus_group"):
            print("Exact bonus optimum:", entry["target_value"],
                  "(matched)" if checked["value"] == entry["target_value"] else "(not yet matched)")
            print("This public bonus case has an exhaustively verified optimum; private cases differ.")
        elif compare:
            target = entry["target_value"]
            print("Public reachable target:", target)
            print(f"Value / target: {checked['value']/target:.1%}" if target else "Target is zero.")
            print("This comparison does not predict a grade or prove optimality.")
    for error in checked["errors"]:
        print(error)
    if result["error"]:
        print(result["error"][-2000:])
    if draw:
        globals()["draw"](entry, checked)
    record = dict(name=entry["name"], runtime=result, checked=checked,
                  public_target=entry["target_value"])
    if entry.get("bonus_group"):
        record.update(bonus_group=entry["bonus_group"],
                      bonus_matched=checked["valid"] and checked["value"] == entry["target_value"])
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true")
    p.add_argument("--case", type=int)
    p.add_argument("--final", action="store_true", help="larger public cases, using the same limits")
    p.add_argument("--bonus", action="store_true", help="exact structured bonus practice instead of the ordinary suite")
    p.add_argument("--module", default=str(Path(__file__).parent/"solver.py"))
    p.add_argument("--seconds", type=float, default=3.)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--compare", action="store_true")
    p.add_argument("--draw", action="store_true")
    p.add_argument("--json", dest="output")
    args = p.parse_args()
    import math
    if not math.isfinite(args.seconds) or args.seconds<=0:
        p.error("--seconds must be positive and finite")
    entries = bonus_cases.catalog(args.final) if args.bonus else catalog(args.final)
    if args.list:
        for i, entry in enumerate(entries, 1):
            c = entry["instance"]
            print(f"{i}. {entry['name']}: {c['height']} x {c['width']}")
        return 0
    if args.case is not None and not 1 <= args.case <= len(entries):
        p.error("case number out of range")
    if args.draw and args.case is None:
        p.error("choose one --case when drawing")
    selected = [entries[args.case-1]] if args.case else entries
    records = [run_case(entry, args.module, args.seconds, args.seed,
                        args.draw, args.compare) for entry in selected]
    if args.bonus and args.case is None:
        print(f"Public bonus practice: {bonus_cases.practice_score(records):.3f}/5.")
        print("The private grader uses different cases with the same group weights and rules.")
        if args.seconds != 3.:
            print("Experimental time allowance; official bonus cases use 3 seconds total search.")
    if args.output:
        Path(args.output).write_text(json.dumps(records, indent=2)+"\n")
    return 0 if all(row["checked"]["valid"] for row in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())

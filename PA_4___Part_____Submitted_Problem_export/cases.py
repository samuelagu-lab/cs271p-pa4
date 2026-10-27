"""Public fixed examples and checked practice witnesses; no grading inputs."""
import json
import itertools
from pathlib import Path

import problem


def make(h, w, blocked=None, weights=None, name="garden"):
    return dict(name=name, height=h, width=w,
                blocked=blocked if blocked is not None else [[False]*w for _ in range(h)],
                weights=weights if weights is not None else [[1]*w for _ in range(h)])


def fixed_cases():
    blocked = [[False]*4 for _ in range(4)]
    blocked[0][0] = True
    return [make(1,1,name="one cell"), make(1,5,name="one row"),
            make(2,2,name="four-cell block"), make(3,3,name="six-cell still life"),
            make(4,4,name="outside-birth boundary check"),
            make(4,4,blocked=blocked,name="blocked corner"),
            make(3,3,weights=[[1,9,2],[7,3,6],[5,8,1]],name="weighted tiny board"),
            make(3,3,blocked=[[True]*3 for _ in range(3)],name="all blocked")]


def catalog(final=False):
    filename = "practice_final_cases.json" if final else "practice_cases.json"
    fixed=[]
    for c in fixed_cases():
        small=c["height"]*c["width"]<=9
        best=problem.empty_board(c)
        score=0
        if small:
            for bits in itertools.product((0,1),repeat=c["height"]*c["width"]):
                board=[list(bits[i*c["width"]:(i+1)*c["width"]]) for i in range(c["height"])]
                ck=problem.check_output(c,board)
                if ck["valid"] and ck["value"]>score:
                    score,best=ck["value"],board
        else:
            # A legal four-cell block is a comparison witness, not an optimum.
            for i in range(c["height"]-1):
                for j in range(c["width"]-1):
                    board=problem.empty_board(c)
                    for a in (i,i+1):
                        for b in (j,j+1): board[a][b]=1
                    ck=problem.check_output(c,board)
                    if ck["valid"]:
                        score,best=ck["value"],board
        fixed.append(dict(name=c["name"],instance=c,target_value=score,target_board=best,
                          tiny_optimum=small,meaning="Exhaustive tiny optimum" if small else "Reachable comparison witness"))
    return fixed+json.loads((Path(__file__).resolve().parent / filename).read_text())

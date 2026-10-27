"""Worked tiny Z3 example, not a general submitted solver.

Run: python3 z3_example.py. It proves the maximum live-cell count on an open
3x3 board by retaining SAT witnesses until a strictly better one is UNSAT.
"""
import z3

import problem


def example():
    instance=dict(height=3,width=3,blocked=[[False]*3 for _ in range(3)],
                  weights=[[1]*3 for _ in range(3)])
    cells=[[z3.Bool(f"live_{i}_{j}") for j in range(3)] for i in range(3)]
    solver=z3.Solver()
    solver.set(timeout=1000)
    # Also constrain the dead ring; an outside birth would change the pattern.
    for i in range(-1,4):
        for j in range(-1,4):
            count=z3.Sum([z3.If(cells[a][b],1,0)
                          for a in range(max(0,i-1),min(3,i+2))
                          for b in range(max(0,j-1),min(3,j+2)) if (a,b)!=(i,j)])
            if 0<=i<3 and 0<=j<3:
                solver.add(cells[i][j]==z3.Or(count==3,z3.And(cells[i][j],count==2)))
            else:
                solver.add(count!=3)
    objective=z3.Sum([z3.If(v,1,0) for row in cells for v in row])
    best=problem.empty_board(instance)
    best_value=0
    while True:
        solver.push()
        solver.add(objective>best_value)
        status=solver.check()
        if status==z3.sat:
            model=solver.model()
            best=[[int(z3.is_true(model.eval(v,model_completion=True))) for v in row] for row in cells]
            checked=problem.check_output(instance,best)
            assert checked["valid"]
            best_value=checked["value"]
        solver.pop()
        if status!=z3.sat:
            return best,best_value,("proved optimum" if status==z3.unsat else "unknown; best witness retained")


if __name__=="__main__":
    board,score,status=example()
    print("Value:",score,"—",status)
    for row in board: print(" ".join(map(str,row)))

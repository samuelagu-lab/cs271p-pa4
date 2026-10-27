"""PA4 solver: Z3 on the whole board, on independent pieces, or on small windows."""
import problem
import z3

SAFETY = 0.15         
BASELINE_SHARE = 0.2     
BASELINE_ON_LARGE = True  
                           
SMALL_CELLS = 100
MEDIUM_CELLS = 260
WHOLE_SHARE = 0.5

WINDOW_SIZES = [(6, 6), (7, 7), (8, 8), (5, 10), (10, 5)]
WINDOW_TIMEOUT = 0.10    
HOTSPOT_PROB = 0.5       
MAX_OFFERS = 60          

USE_PB = True

EXACT_COMPONENT_CELLS = 50   
COMPONENT_SHARE = 0.6   
COMPONENT_TIMEOUT = 0.6  

def count_is(var_cells, fixed, k):
    """Z3 condition: the true var_cells plus `fixed` live neighbors (counted in Python) equal k."""
    need = k - fixed
    if need < 0 or need > len(var_cells):
        return z3.BoolVal(False)
    if not var_cells:
        return z3.BoolVal(need == 0)
    if USE_PB:
        return z3.PbEq([(v, 1) for v in var_cells], need)
    return z3.Sum([z3.If(v, 1, 0) for v in var_cells]) == need


def at_least(terms, k):
    """Z3 condition: the total weight of true variables in terms = [(var, weight)] is >= k."""
    if k <= 0:
        return z3.BoolVal(True)
    if not terms:
        return z3.BoolVal(False)
    if USE_PB:
        return z3.PbGe(terms, k)
    return z3.Sum([z3.If(v, wt, 0) for v, wt in terms]) >= k


def build_model(instance, board=None, window=None):
    """Z3 model for window = (top, left, h, w), with every other cell fixed at its `board`
    value and folded into the rules as a constant. Rules cover the window and ring 1;
    returns (cells, solver), where cells[r][c] is board cell (top + r, left + c)."""
    H, W = instance["height"], instance["width"]
    if window is None:
        window = (0, 0, H, W)
    top, left, h, w = window
    if board is None:
        board = problem.empty_board(instance)
    blocked = instance["blocked"]

    cells = [[z3.Bool(f"live_{top + r}_{left + c}") for c in range(w)]
             for r in range(h)]

    def in_window(a, b):
        return top <= a < top + h and left <= b < left + w

    solver = z3.Solver()
    # Window plus ring 1, clipped to the board and its one-cell outside ring.
    for i in range(max(-1, top - 1), min(H, top + h) + 1):
        for j in range(max(-1, left - 1), min(W, left + w) + 1):
            var_nbrs, fixed = [], 0
            for a in range(max(0, i - 1), min(H, i + 2)):
                for b in range(max(0, j - 1), min(W, j + 2)):
                    if (a, b) == (i, j):
                        continue
                    if in_window(a, b):
                        var_nbrs.append(cells[a - top][b - left])
                    else:
                        fixed += board[a][b]
            three = count_is(var_nbrs, fixed, 3)
            if not (0 <= i < H and 0 <= j < W):
                solver.add(z3.Not(three))                    # off the board: no births
            elif in_window(i, j):
                me = cells[i - top][j - left]
                two = count_is(var_nbrs, fixed, 2)
                solver.add(z3.Implies(me, z3.Or(two, three)))  # live: 2 or 3 neighbors
                solver.add(z3.Implies(z3.Not(me), z3.Not(three)))  # dead: not exactly 3
                if blocked[i][j]:
                    solver.add(z3.Not(me))
            elif board[i][j]:
                solver.add(z3.Or(count_is(var_nbrs, fixed, 2), three))  # fixed live cell
            else:
                solver.add(z3.Not(three))                    # fixed dead cell
    return cells, solver


def score_terms(instance, cells, top=0, left=0):
    """(variable, weight) pairs for the window's cells, which form the objective."""
    weights = instance["weights"]
    return [(v, weights[top + r][left + c])
            for r, row in enumerate(cells) for c, v in enumerate(row)]


def window_value(instance, board, top, left, h, w):
    """Current total weight of live cells inside the window, in plain Python."""
    weights = instance["weights"]
    return sum(weights[i][j] for i in range(top, top + h)
               for j in range(left, left + w) if board[i][j])


def decode(model, cells, board=None, top=0, left=0):
    """Return a copy of `board` (or an empty board) with the window set to the model's values."""
    if board is None:
        out = [[0] * len(cells[0]) for _ in cells]
    else:
        out = [row[:] for row in board]
    for r, row in enumerate(cells):
        for c, v in enumerate(row):
            out[top + r][left + c] = int(z3.is_true(model.eval(v, model_completion=True)))
    return out


def block_baseline(instance, budget, rng, stop_at):
    """The starter's method: add 2x2 blocks that keep the board legal, until
    budget.remaining() drops below stop_at."""
    board = problem.empty_board(instance)
    sites = [(i, j) for i in range(instance["height"] - 1)
             for j in range(instance["width"] - 1)]
    rng.shuffle(sites)
    for i, j in sites:
        if budget.remaining() < stop_at:
            break
        block = [(a, b) for a in (i, i + 1) for b in (j, j + 1)]
        if any(board[a][b] or instance["blocked"][a][b] for a, b in block):
            continue
        for a, b in block:
            board[a][b] = 1
        if not problem.check_output(instance, board)["valid"]:
            for a, b in block:
                board[a][b] = 0
    return board


class Offers:
    """Offers improving boards under the grader's 64-offer limit, keeping the last
    slots so the final best is always saved."""
    def __init__(self, budget):
        self.budget, self.count, self.pending = budget, 0, None

    def improved(self, board):
        if self.count < MAX_OFFERS - 2:
            self.count += 1
            self.budget.offer(board)
            self.pending = None
        else:
            self.pending = board

    def flush(self):
        if self.pending is not None and self.count < MAX_OFFERS:
            self.count += 1
            self.budget.offer(self.pending)
            self.pending = None


def search(instance, budget, offers, cells, solver, terms,
           best_board, best_value, stop_at=0.0):
    """Whole-board loop asking Z3 for strictly better boards until unsat, unknown or
    budget.remaining() reaches stop_at. Returns (board, value, proven_optimal)."""
    while True:
        left = budget.remaining() - max(SAFETY, stop_at)
        if left <= 0.05:
            return best_board, best_value, False
        solver.set(timeout=int(left * 1000))
        solver.push()
        solver.add(at_least(terms, best_value + 1))
        status = solver.check()
        board = decode(solver.model(), cells) if status == z3.sat else None
        solver.pop()
        if board is None:
            return best_board, best_value, status == z3.unsat
        checked = problem.check_output(instance, board)
        if not checked["valid"]:
            return best_board, best_value, False   # should never happen
        best_board, best_value = board, checked["value"]
        offers.improved(best_board)


def pick_window(instance, rng, hot_cells, hot_weights, centered):
    """Choose a window (top, left, h, w), centered half the time on a weight-sampled cell.
    When `centered` is True, every window is centered on a hot cell, away from proven pieces."""
    H, W = instance["height"], instance["width"]
    h, w = rng.choice(WINDOW_SIZES)
    h, w = min(h, H), min(w, W)
    if hot_cells and (centered or rng.random() < HOTSPOT_PROB):
        if centered and rng.random() >= HOTSPOT_PROB:
            ci, cj = rng.choice(hot_cells)
        else:
            ci, cj = rng.choices(hot_cells, weights=hot_weights)[0]
        top = min(max(0, ci - h // 2), H - h)
        left = min(max(0, cj - w // 2), W - w)
    else:
        top, left = rng.randint(0, H - h), rng.randint(0, W - w)
    return top, left, h, w


def contains(outer, inner):
    """True if rectangle `inner` lies inside rectangle `outer` (top, left, h, w)."""
    ot, ol, oh, ow = outer
    it, il, ih, iw = inner
    return ot <= it and ol <= il and it + ih <= ot + oh and il + iw <= ol + ow


def near(rect, changed):
    """True if `changed` overlaps `rect` grown by 2 cells, the only changes that can
    affect `rect`'s model."""
    t, l, h, w = rect
    ct, cl, ch, cw = changed
    return ct < t + h + 2 and t - 2 < ct + ch and cl < l + w + 2 and l - 2 < cl + cw


def window_search(instance, budget, rng, offers, best_board, best_value, frozen=()):
    """Repeatedly re-optimize one window with the rest of the board fixed, keeping it legal.
    Proven-unimprovable windows (and windows inside them) are skipped until a change lands
    within 2 cells, and `frozen` cells are never used as centers."""
    H, W = instance["height"], instance["width"]
    blocked = instance["blocked"]
    frozen = set(frozen)
    hot_cells = [(i, j) for i in range(H) for j in range(W)
                 if not blocked[i][j] and (i, j) not in frozen]
    hot_weights = [instance["weights"][i][j] for i, j in hot_cells]
    if not hot_cells:
        return best_board, best_value               # nothing left that can change
    centered = bool(frozen)
    settled = []                                    # windows proven unimprovable
    skips = 0
    while True:
        if budget.remaining() - SAFETY <= 0.05:
            break
        rect = pick_window(instance, rng, hot_cells, hot_weights, centered)
        if skips < 50 and any(contains(f, rect) for f in settled):
            skips += 1                              # known unimprovable; pick again
            continue
        skips = 0
        top, left, h, w = rect
        cells, solver = build_model(instance, best_board, rect)
        candidate, proven = improve_window(instance, budget, best_board, cells, solver,
                                           top, left, h, w)
        if candidate is None:
            if proven:
                settled.append(rect)
            continue                                 # no better filling for this window
        checked = problem.check_output(instance, candidate)
        if checked["valid"] and checked["value"] > best_value:
            best_board, best_value = candidate, checked["value"]
            offers.improved(best_board)
            settled = [f for f in settled if not near(f, rect)]
            if proven:
                settled.append(rect)                 # this window is now locally optimal
    return best_board, best_value


def improve_window(instance, budget, board, cells, solver, top, left, h, w):
    """Raise the bar on one window's model until Z3 says unsat, times out, or WINDOW_TIMEOUT
    runs out. Returns (best full board or None, proven), proven meaning locally optimal."""
    terms = score_terms(instance, cells, top, left)
    bar = window_value(instance, board, top, left, h, w)
    window_deadline = budget.remaining() - WINDOW_TIMEOUT    # in "remaining" terms
    best = None
    while True:
        left_time = budget.remaining() - SAFETY
        window_time = budget.remaining() - window_deadline
        timeout = min(left_time, WINDOW_TIMEOUT, window_time)
        if timeout <= 0.01:
            return best, False
        solver.set(timeout=int(timeout * 1000))
        solver.push()
        solver.add(at_least(terms, bar + 1))
        status = solver.check()
        candidate = decode(solver.model(), cells, board, top, left) if status == z3.sat else None
        solver.pop()
        if candidate is None:
            return best, status == z3.unsat         # unsat: window optimal; unknown: out of time
        best = candidate
        bar = window_value(instance, candidate, top, left, h, w)


def components(instance):
    """Split the free cells into groups sharing no rule, linking cells within king-move
    distance 2. A one-cell blocked wall does not separate rooms; a two-cell wall does."""
    H, W = instance["height"], instance["width"]
    blocked = instance["blocked"]
    seen = [[False] * W for _ in range(H)]
    comps = []
    for si in range(H):
        for sj in range(W):
            if blocked[si][sj] or seen[si][sj]:
                continue
            seen[si][sj] = True
            stack, comp = [(si, sj)], []
            while stack:
                i, j = stack.pop()
                comp.append((i, j))
                for a in range(max(0, i - 2), min(H, i + 3)):
                    for b in range(max(0, j - 2), min(W, j + 3)):
                        if not blocked[a][b] and not seen[a][b]:
                            seen[a][b] = True
                            stack.append((a, b))
            comps.append(comp)
    return comps


def solve_component(instance, budget, comp, start_board, time_cap):
    """Exact improvement loop for one piece, with every other cell dead, starting from
    start_board. Returns (assignment {cell: 0/1} or None if start_board's part is best, proven)."""
    rows = [i for i, _ in comp]
    cols = [j for _, j in comp]
    top, left = min(rows), min(cols)
    bbox = (top, left, max(rows) - top + 1, max(cols) - left + 1)
    comp_set = set(comp)
    cells, solver = build_model(instance, problem.empty_board(instance), bbox)
    for r, row in enumerate(cells):
        for c, v in enumerate(row):
            if (top + r, left + c) not in comp_set:
                solver.add(z3.Not(v))               # cells of other pieces: off here
    weights = instance["weights"]
    terms = [(cells[i - top][j - left], weights[i][j]) for i, j in comp]
    bar = sum(weights[i][j] for i, j in comp if start_board[i][j])
    deadline = budget.remaining() - time_cap
    best = None
    while True:
        timeout = min(budget.remaining() - SAFETY, budget.remaining() - deadline)
        if timeout <= 0.01:
            return best, False
        solver.set(timeout=int(timeout * 1000))
        solver.push()
        solver.add(at_least(terms, bar + 1))
        status = solver.check()
        if status == z3.sat:
            model = solver.model()
            best = {(i, j): int(z3.is_true(model.eval(cells[i - top][j - left],
                                                      model_completion=True)))
                    for i, j in comp}
            bar = sum(weights[i][j] for (i, j), on in best.items() if on)
        solver.pop()
        if status != z3.sat:
            return best, status == z3.unsat


def solve_components(instance, budget, offers, comps, best_board, best_value):
    """Exactly solve the small independent pieces, smallest first, within a share of the
    time. Returns (board, value, frozen cells, all_proven)."""
    small = sorted((c for c in comps if len(c) <= EXACT_COMPONENT_CELLS), key=len)
    phase_end = budget.remaining() * (1 - COMPONENT_SHARE)
    board = [row[:] for row in best_board]
    frozen, proven_all = [], len(small) == len(comps)
    for k, comp in enumerate(small):
        left_time = budget.remaining() - max(SAFETY, phase_end)
        if left_time <= 0.02:
            proven_all = False
            break
        cap = min(COMPONENT_TIMEOUT, left_time / (len(small) - k))
        assignment, proven = solve_component(instance, budget, comp, board, cap)
        if assignment is not None:
            for (i, j), on in assignment.items():
                board[i][j] = on
        if proven:
            frozen.extend(comp)
        else:
            proven_all = False
    checked = problem.check_output(instance, board)
    if not checked["valid"] or checked["value"] < best_value:
        return best_board, best_value, [], False   # should never happen; keep old board
    if checked["value"] > best_value:
        offers.improved(board)
    return board, checked["value"], frozen, proven_all


def solve(instance, budget, rng):
    offers = Offers(budget)
    best = problem.empty_board(instance)
    budget.offer(best)
    offers.count += 1
    value = 0

    n = instance["height"] * instance["width"]
    if n <= MEDIUM_CELLS or BASELINE_ON_LARGE:
        stop_at = budget.remaining() * (1 - BASELINE_SHARE)
        baseline = block_baseline(instance, budget, rng, stop_at)
        baseline_value = problem.check_output(instance, baseline)["value"]
        if baseline_value > 0:
            best, value = baseline, baseline_value
            offers.improved(best)

    frozen = []
    comps = components(instance)
    if len(comps) >= 2:
        best, value, frozen, proven_all = solve_components(
            instance, budget, offers, comps, best, value)
        if proven_all:
            offers.flush()
            return best

    if n <= MEDIUM_CELLS and not frozen:
        whole_stop = 0.0 if n <= SMALL_CELLS else budget.remaining() * (1 - WHOLE_SHARE)
        cells, solver = build_model(instance)
        terms = score_terms(instance, cells)
        best, value, proven = search(instance, budget, offers, cells, solver,
                                     terms, best, value, stop_at=whole_stop)
        if proven:
            offers.flush()
            return best

    # Window search for the rest of the time, away from proven-optimal pieces.
    best, value = window_search(instance, budget, rng, offers, best, value, frozen)
    offers.flush()
    return best

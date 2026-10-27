CS 271P — PA 4: Weighted Stable Garden
Part 2 — Submitted Problem

Read "PA 4 - Weighted Stable Garden - Submission Instructions.pdf" for the full
specification. This README also gives the complete programming/grading contract.
Submit ONE file named solver.py on Gradescope. Tutorials, the optional Z3 Primer
and the Garden notebook are not submitted. Keep the supplied helper files unchanged.

TASK
  Implement solve(instance, budget, rng). Return your best legal stable pattern.
  instance contains height, width, blocked and weights. Dimensions are positive
  ordinary integers; blocked is a matching Boolean matrix; weights is a matching
  matrix of positive ordinary integers. You receive no category label or target.
  Return an ordinary Python list of rows of ordinary integer 0/1 values. Boolean
  values, tuples, NumPy arrays and Z3 values are not the submission format.

  Each cell has up to eight horizontal/vertical/diagonal neighbors. After one step:
    exactly three live neighbors -> alive;
    exactly two -> keep the current state;
    otherwise -> dead.
  Your entire pattern must be unchanged. Every blocked cell is dead AND cannot
  have exactly three live neighbors. Cells outside the rectangle are dead and
  must remain dead; checking the surrounding one-cell ring is sufficient.
  Maximize the sum of weights of live cells. The empty board is always legal.

Z3 AND STARTING POINT
  Python 3.10 or newer. Use the standard library and Z3's Python integration,
  installed as z3-solver and imported as z3. This is the only external constraint
  solver in the grading environment. Do not use another external solver.
  python3 -m pip install -r requirements.txt
  New to Z3? Open Z3 Primer.ipynb and Run All (about 20 minutes, optional).
  It teaches choices, logical rules, counts, weighted sums, reading models,
  SAT/UNSAT/unknown, timeouts and a simple value-improvement loop through a small
  science-booth problem. Try two one-line changes and compare the pictures.
  No extra packages, widgets or deliverables are needed. A short checklist helps
  you apply the commands; you write the Garden constraints yourself. Advanced
  Z3 features are mentioned, without covering advanced Garden implementations.
  Then run python3 z3_example.py to inspect the separate tiny Garden example.
  The worked 3x3 example distinguishes a SAT witness, a proven optimum and unknown.
  The starter adds checked 2x2 blocks. It is intentionally incomplete: it does not
  find every tiny optimum or optimize general weighted patterns. You may replace
  it, formulate a Z3 model, try ordering or decomposition, or improve a local patch.
  Your general solve implementation must live entirely in the one submitted file.
  You may import the supplied problem.py for legality/value checks.

RESOURCE CONTRACT (LOCAL, REGULAR AND FINAL)
  Module import: 10 seconds wall time, separately. Do not solve at import time.
  solve: 3 seconds wall time TOTAL, including preprocessing, model construction,
  search, checking offers, serialization and return. Use one search thread.
  On the Linux grader, each worker has a 1 GiB virtual-address-space limit.
  Only solver.py is submitted; no auxiliary files, precomputed answer databases,
  network access, subprocess solvers or reads of private grader files are allowed.
  Small reusable stable shapes are fine; do not hardcode full boards for test inputs.
  rng is a supplied random.Random instance. budget.remaining() gives seconds left;
  budget.expired() reports expiration. Set a native Z3 timeout below the remaining
  budget, leave time to decode/check/return, and stop on unknown without claiming
  infeasibility or optimality. Construction time counts too.

  budget.offer(board) saves a checked improving board while time remains. It
  returns True if accepted and False otherwise. At most 64 improving offers can
  be saved. Offer the empty board promptly, then improvements. Return your best
  board too. A saved legal board survives a late return, invalid return or later
  exception; the highest-value accepted board or valid timely return is used.
  A board displayed by the notebook as a fallback is not an answer from your file.
  Each case uses a fresh process and imports the current source, without stale .pyc.

GRADING — 100 AUTOMATIC POINTS, PLUS UP TO 5 BONUS POINTS
  30 validity: 15 for the eight public fixed examples, 15 for private small
     generated 5x6 boards. Points within each group are divided equally.
  20 exact tiny optimum: equally divided over the six public fixed boards with
     at most nine cells. An independent exhaustive oracle verifies the optimum.
  50 quality: equally divided over ten categories, and equally over cases within
     each category. For a legal board with value V and positive target T:
       quality fraction = min(1, V / (0.98 * T)).
     An invalid/missing board receives zero for that case. Empty performance
     boards are legal but earn zero quality points. Exceeding a target is welcome.
     Targets are legal Z3 staff boards, frozen before grading. Each target is the
     lowest checked value from THREE reference searches, each under the same
     3-second search / 10-second import / one-thread allowance as students.
     A reachable target is not a proof of the true optimum. No staff search runs
     during grading. Private instances and targets are omitted from student files.

  Regular: 10 generated validity cases, 2 quality cases per category (20 total).
  FINAL: 20 generated validity cases, 4 quality cases per category (40 total),
  generally larger grids. Same fixed cases, interface, rules, points and time
  allowance. After all submissions are in, FINAL replaces the regular grade.
  Public correctness feedback is visible. Private quality feedback is released
  after grades are published. A local VALID result establishes legality only;
  the local public target comparison does not predict a grade.

BONUS — EXACT ANSWERS ON SMALL STRUCTURED GARDENS (UP TO 5 AUTOMATIC POINTS)
  4 points: find the exact optimum on boards made of several small rooms.
    Regular boards contain six 4x4 rooms in a 10x16 rectangle; FINAL contains
    eight in a 10x22 rectangle. Blocked rows and columns separate the rooms,
    and a room may contain blocked cells. Weights are 1..12.
  1 point: find the exact optimum on two open 3x3 rooms with ONE blocked
    column between them: a 3x7 rectangle with 18 free cells. FINAL uses more
    cases of the same size.
  Boards may be transposed/reflected. Regular has two private cases per group;
  FINAL has four per group. Each group's points are divided equally over its
  cases: an exact result earns the case's points; suboptimal, invalid or missing
  output earns zero for that bonus case. Partial credit accumulates across cases.
  Bonus points are added to the ordinary score, even if it is below 100. The
  assignment total stays 100 and the maximum reported score is 105.

  A garden with this structure may break into pieces that can be solved
  separately and put together. Whether that is ever safe under the stability
  rules, which pieces are safe to separate, and how to combine them, is for
  you to work out. Check every whole board you build.
  Any correct method earns the same points; no specific implementation is required.
  These bonus optima are independently exhaustively verified, unlike the large
  quality targets. Small complete Z3 models can prove their optima by showing
  that no strictly better pattern exists. You submit only a board, not a proof.
  The same solve API, 3-second TOTAL search, 10-second import, one-thread and
  memory limits apply. No extra file, notebook or written response is submitted.
  Exact private inputs remain private; analogous public bonus cases have exact
  optima and checked witnesses, with the same sizes, weights, rules and limits.

TEN ASSESSED CATEGORIES (dimensions may be transposed/reflected)
  Category             Regular dimensions       FINAL dimensions
  control_scattered    18x20                     22x24
  control_bands        18x20                     22x24
  long_strip           36x4                      44x5
  open_square          20..22 x 22..24            24..26 x 26..28
  irregular_islands    18x20                     22x24
  thin_walls           18x20                     22x24
  connected_rooms      18x20                     22x24
  hotspots             18x20                     22x24
  wider_strip          36x6                      44x7
  mixed_components     26x30                     30x34

  Scattered inputs have random blocked cells; bands have two-cell-wide blocked
  separators. Strips emphasize a long narrow shape. Open rectangles have uniform
  weights. Islands contain irregular separated rooms. Thin walls are one blocked
  cell wide. Connected rooms have corridors. Hotspots contain high-value patches.
  Mixed components combine several narrow rooms separated by blocked rows and
  columns. Most ordinary weights
  are 1..12; hotspot weights can reach 301. No hidden category introduces a new
  rule, negative weight, mandatory live cell or new API.

LOCAL CHECKS
  python3 test_local.py                         # all 18 regular public cases
  python3 test_local.py --list                  # list without importing solver
  python3 test_local.py --case 4 --compare      # exact tiny example
  python3 test_local.py --case 18 --compare     # mixed components
  python3 test_local.py --final --compare       # 28 public FINAL cases
  python3 test_local.py --module path/to/solver.py --compare --json results.json
  python3 test_local.py --seed 123              # repeat the solver's randomness
  python3 test_local.py --case 18 --compare --draw
  python3 test_local.py --bonus --list         # four public regular bonus cases
  python3 test_local.py --bonus                # public bonus practice score /5
  python3 test_local.py --bonus --case 1 --draw # inspect one structured case
  python3 test_local.py --bonus --final        # eight public FINAL bonus cases
  The cases are fixed public representatives; --seed changes solver randomness.
  --seconds can change the local allowance for experiments; the grader always
  uses 3 seconds. Core text tests use standard Python; Z3 is needed by Z3 solutions.
  --bonus selects bonus practice instead of the ordinary suite. A full bonus
  run reports an analogous /5 score; a single-case run reports the exact target
  and whether you matched it. This diagnoses public cases, not your private grade.

OPTIONAL VISUAL EXPLORATION (about five minutes)
  pip install -r requirements-visual.txt
  Open Explore Garden.ipynb, Run All, select a preset, then press Run saved solver.py.
  Predict -> inspect blocked cells/weights -> compare a checked board -> explain
  one change. Preset selection does not run your solver. Static examples/text CLI
  work without widgets/plots. No screenshot or notebook submission is required.

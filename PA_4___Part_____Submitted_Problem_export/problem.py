"""Public independent checker for blocked, weighted stable Life patterns."""
KIND = "garden"


def validate_instance(c):
    h, w = c["height"], c["width"]
    if type(h) is not int or type(w) is not int or h < 1 or w < 1:
        raise ValueError("positive integer grid dimensions required")
    for key in ("blocked", "weights"):
        matrix = c[key]
        if type(matrix) is not list or len(matrix) != h or any(type(row) is not list or len(row) != w for row in matrix):
            raise ValueError(key+" must match the grid")
    if any(type(v) is not bool for row in c["blocked"] for v in row):
        raise ValueError("blocked entries are bools")
    if any(type(v) is not int or v < 1 for row in c["weights"] for v in row):
        raise ValueError("positive ordinary integer cell weights required")


def empty_board(c):
    return [[0]*c["width"] for _ in range(c["height"])]


def check_output(c, board):
    h, w = c["height"], c["width"]
    if type(board) is not list or len(board) != h or any(type(row) is not list or len(row) != w for row in board):
        return dict(valid=False, errors=["Return a list of rows matching the grid"], value=None)
    if any(type(v) is not int or v not in (0, 1) for row in board for v in row):
        return dict(valid=False, errors=["Each cell must be an ordinary integer 0 or 1"], value=None)
    errors = []
    for i in range(-1, h+1):
        for j in range(-1, w+1):
            inside = 0 <= i < h and 0 <= j < w
            current = board[i][j] if inside else 0
            count = sum(board[a][b] for a in range(max(0, i-1), min(h, i+2))
                        for b in range(max(0, j-1), min(w, j+2)) if (a, b) != (i, j))
            next_cell = int(count == 3 or (current == 1 and count == 2))
            if current != next_cell:
                errors.append(f"cell ({i},{j}) changes from {current} to {next_cell} ({count} live neighbours)")
            if inside and current and c["blocked"][i][j]:
                errors.append(f"blocked cell ({i},{j}) is live")
    value = sum(board[i][j]*c["weights"][i][j] for i in range(h) for j in range(w))
    return dict(valid=not errors, errors=errors[:12], value=value if not errors else None)


def description(c):
    return f"{c['height']}×{c['width']} board, {sum(sum(row) for row in c['blocked'])} blocked cells"

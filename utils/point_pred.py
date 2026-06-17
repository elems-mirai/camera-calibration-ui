import numpy as np

def predict_checkerboard_points(P1, P2, rows, cols, return_all=False,
                                selected_indices=(0, 4, 35, 39, 17),
                                y_increases_down=True, cell_size=None):
    """
    Compute checkerboard inner-corner coordinates for a rotated board.

    Parameters
    ----------
    P1 : (x, y)
        Bottom-left inner corner (measured).
    P2 : (x, y)
        Bottom-right inner corner (measured). May have different y than P1.
    rows : int
        Number of rows (vertical count of inner corners).
    cols : int
        Number of columns (horizontal count of inner corners).
    return_all : bool
        If True, returns all rows*cols points (row-major, bottom→top).
        Otherwise returns the points at `selected_indices`.
    selected_indices : iterable
        Indices (row-major) to return when `return_all=False`.
    y_increases_down : bool
        True for image coordinates (y grows downward). False for math coords (y up).
        Used to auto-pick the correct “down” direction.
    cell_size : float or None
        Optional override for square cell size. If None, it is inferred from |P2-P1|/(cols-1).

    Returns
    -------
    np.ndarray
        (rows*cols, 2) if return_all, else (len(selected_indices), 2).
    """
    P1 = np.asarray(P1, dtype=float)
    P2 = np.asarray(P2, dtype=float)

    # --- Horizontal (right) direction from P1 to P2 ---
    right_vec = P2 - P1
    right_len = np.linalg.norm(right_vec)
    if right_len == 0:
        raise ValueError("P1 and P2 must be different points.")

    right_unit = right_vec / right_len

    # --- Cell size (assume square cells unless provided) ---
    if cols < 2:
        raise ValueError("cols must be >= 2")
    step = (right_len / (cols - 1)) if cell_size is None else float(cell_size)

    # --- Perpendicular (“down”) direction (choose sign automatically) ---
    # CCW ⟂: (-y, x) ;  CW ⟂: (y, -x)
    down_ccw = np.array([-right_unit[1],  right_unit[0]])
    down_cw  = np.array([ right_unit[1], -right_unit[0]])

    # Choose the one that makes rows advance in the intended y direction.
    # We want (P1 + (rows-1)*step*down_unit).y  >  P1.y  if y_increases_down (image coords)
    # or < P1.y if y increases upward (math coords).
    cand_ccw_y = (P1 + (rows - 1) * step * down_ccw)[1]
    if y_increases_down:
        down_unit = down_ccw if cand_ccw_y > P1[1] else down_cw
    else:
        down_unit = down_ccw if cand_ccw_y < P1[1] else down_cw

    # --- Build the grid (row-major: row=0 is bottom, row increases downward if y_increases_down=True) ---
    pts = np.empty((rows * cols, 2), dtype=float)
    idx = 0
    for r in range(rows):
        base = P1 + r * step * down_unit
        for c in range(cols):
            pts[idx] = base + c * step * right_unit
            idx += 1

    if return_all:
        return pts
    return pts[np.array(list(selected_indices), dtype=int)]

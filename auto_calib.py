import cv2
import numpy as np
import csv
import os
import glob

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
CHESSBOARD_SIZE  = (10, 4)
SQUARE_SIZE      = 20.0
POINTS_PER_IMAGE = 5

# Starting corner: "LT", "RT", "LB", "RB"
#   LT = Left-Top      RT = Right-Top
#   LB = Left-Bottom    RB = Right-Bottom
ANCHOR_CORNER = "RT"

# From the anchor point, which direction does each axis increase?
# X (vertical):   "UP" or "DOWN"
# Y (horizontal): "LEFT" or "RIGHT"
X_INCREASES = "UP"
Y_INCREASES = "LEFT"

# World coordinate value at the anchor corner
ANCHOR_X = -25.0
ANCHOR_Y = 25

CAM1_IMAGE_FOLDER = "./SHINMEI_DEMO/back/extrinsic_images/capture_20260417_134942.jpg"
CAM2_IMAGE_FOLDER = "./SHINMEI_DEMO/front/extrinsic_images/capture_20260417_134950.jpg"

OUTPUT_CSV_CAM1 = "./SHINMEI_DEMO/back/points.csv"
OUTPUT_CSV_CAM2 = "./SHINMEI_DEMO/front/points.csv"

OUTPUT_VIS_CAM1 = "./SHINMEI_DEMO/back/vis_cam1/"
OUTPUT_VIS_CAM2 = "./SHINMEI_DEMO/front/vis_cam2/"

detection_flags = (
    cv2.CALIB_CB_ADAPTIVE_THRESH +
    cv2.CALIB_CB_NORMALIZE_IMAGE +
    cv2.CALIB_CB_FAST_CHECK
)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)


# ─────────────────────────────────────────────
# REORDER CORNERS
# ─────────────────────────────────────────────
def reorder_corners(corners, num_cols, num_rows, anchor_corner="RB"):
    """
    Reorder detected corners so that index 0 is at the chosen anchor corner.

    anchor_corner:
      "LT" = Left-Top      "RT" = Right-Top
      "LB" = Left-Bottom    "RB" = Right-Bottom

    After reordering:
      - Row direction (index += num_cols) moves AWAY from anchor vertically
      - Col direction (index += 1)        moves AWAY from anchor horizontally
    """
    anchor_corner = anchor_corner.upper()
    if anchor_corner not in ("LT", "RT", "LB", "RB"):
        raise ValueError(f"Invalid anchor_corner '{anchor_corner}'. Use LT, RT, LB, RB.")

    want_right  = "R" in anchor_corner
    want_bottom = "B" in anchor_corner

    corners = corners.reshape(num_rows, num_cols, 1, 2).copy()

    # Check current layout from pixel coordinates
    top_left_px    = corners[0, 0, 0]       # first row, first col
    top_right_px   = corners[0, -1, 0]      # first row, last col
    bottom_left_px = corners[-1, 0, 0]      # last row, first col

    # Does row index increasing go downward in pixel space?
    rows_go_down = bottom_left_px[1] > top_left_px[1]
    # Does col index increasing go rightward in pixel space?
    cols_go_right = top_right_px[0] > top_left_px[0]

    # Flip rows so row=0 is at the desired vertical side
    if want_bottom and not rows_go_down:
        corners = corners[::-1, :, :, :]
    elif not want_bottom and rows_go_down:
        corners = corners[::-1, :, :, :]

    # Flip cols so col=0 is at the desired horizontal side
    if want_right and not cols_go_right:
        corners = corners[:, ::-1, :, :]
    elif not want_right and cols_go_right:
        corners = corners[:, ::-1, :, :]

    return corners.reshape(-1, 1, 2).copy()


# ─────────────────────────────────────────────
# AUTO-GENERATE WORLD COORDINATES
# ─────────────────────────────────────────────
num_cols, num_rows = CHESSBOARD_SIZE

# After reorder_corners(), the layout is:
#   row increases = moves AWAY from anchor vertically
#   col increases = moves AWAY from anchor horizontally
#
# "Away from anchor vertically":
#   anchor at Bottom → away = UP
#   anchor at Top    → away = DOWN
#
# "Away from anchor horizontally":
#   anchor at Right → away = LEFT
#   anchor at Left  → away = RIGHT

away_vertical   = "UP"    if "B" in ANCHOR_CORNER.upper() else "DOWN"
away_horizontal = "LEFT"  if "R" in ANCHOR_CORNER.upper() else "RIGHT"

x_sign = +1 if X_INCREASES.upper() == away_vertical   else -1
y_sign = +1 if Y_INCREASES.upper() == away_horizontal else -1

world_coords = []
for row in range(num_rows):
    for col in range(num_cols):
        xw = ANCHOR_X + x_sign * row * SQUARE_SIZE
        yw = ANCHOR_Y + y_sign * col * SQUARE_SIZE
        world_coords.append((xw, yw))

total_corners = len(world_coords)

# Sanity print
print(f"Anchor corner : {ANCHOR_CORNER}")
print(f"X increases   : {X_INCREASES}")
print(f"Y increases   : {Y_INCREASES}")
print(f"Total corners : {total_corners}")
print(f"  index 0 (anchor)  : Xw={world_coords[0][0]:.1f}, Yw={world_coords[0][1]:.1f}")
print(f"  index {num_cols-1} (end col)  : Xw={world_coords[num_cols-1][0]:.1f}, Yw={world_coords[num_cols-1][1]:.1f}")
print(f"  index {(num_rows-1)*num_cols} (end row) : Xw={world_coords[(num_rows-1)*num_cols][0]:.1f}, Yw={world_coords[(num_rows-1)*num_cols][1]:.1f}")
print()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def make_virtual_names(base_name, total_pts, pts_per_img):
    stem, ext = os.path.splitext(base_name)
    slices = []
    chunk, start = 0, 0
    while start < total_pts:
        end = min(start + pts_per_img, total_pts)
        chunk += 1
        slices.append((f"{stem}_p{chunk:02d}{ext}", start, end))
        start = end
    return slices


# ─────────────────────────────────────────────
# CORE PROCESSING
# ─────────────────────────────────────────────
def process_camera(image_folder, output_csv, output_vis_folder, cam_label):
    os.makedirs(output_vis_folder, exist_ok=True)

    if os.path.isdir(image_folder):
        image_paths = sorted(
            glob.glob(os.path.join(image_folder, "*.jpg")) +
            glob.glob(os.path.join(image_folder, "*.png"))
        )
    elif os.path.isfile(image_folder):
        image_paths = [image_folder]
    else:
        image_paths = []

    if not image_paths:
        print(f"⚠️  {cam_label}: No images found in {image_folder}")
        return

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image_name", "points", "xi", "yi", "xw", "yw"])

        for img_path in image_paths:
            img_name = os.path.basename(img_path)
            img      = cv2.imread(img_path)
            gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, detection_flags)
            if ret:
                corners = cv2.cornerSubPix(gray, corners, (3, 3), (-1, -1), criteria)
                corners = reorder_corners(corners, num_cols, num_rows, ANCHOR_CORNER)
                print(f"✓ {cam_label} | {img_name} | {total_corners} corners detected")
            else:
                print(f"✗ {cam_label} | {img_name} | NOT DETECTED")

            slices = make_virtual_names(img_name, total_corners, POINTS_PER_IMAGE)

            for virtual_name, g_start, g_end in slices:
                cv2.imwrite(os.path.join(output_vis_folder, virtual_name), img.copy())

                local_pt = 1
                for global_i in range(g_start, g_end):
                    xw, yw = world_coords[global_i]
                    if ret:
                        xi = corners[global_i][0][0]
                        yi = corners[global_i][0][1]
                        writer.writerow([virtual_name, local_pt,
                                         f"{xi:.4f}", f"{yi:.4f}",
                                         f"{xw:.4f}", f"{yw:.4f}"])
                    else:
                        writer.writerow([virtual_name, local_pt,
                                         "", "",
                                         f"{xw:.4f}", f"{yw:.4f}"])
                    local_pt += 1

    print(f"\n   CSV    → {output_csv}")
    print(f"   Images → {output_vis_folder}\n")


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
process_camera(CAM1_IMAGE_FOLDER, OUTPUT_CSV_CAM1, OUTPUT_VIS_CAM1, "Camera 1")
process_camera(CAM2_IMAGE_FOLDER, OUTPUT_CSV_CAM2, OUTPUT_VIS_CAM2, "Camera 2")

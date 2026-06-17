import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyArrowPatch
import os

# ─────────────────────────────────────────────
# CONFIGURATION  – match your calibration setup
# ─────────────────────────────────────────────
CHESSBOARD_SIZE = (10, 4)
SQUARE_SIZE     = 20.0

CSV_BACK  = "./2_1_camera/back/points.csv"
CSV_FRONT = "./2_1_camera/front/points.csv"

# Intrinsics – replace with your actual K & dist per camera
# Shape: (3,3) and (1,5) or (1,4)
K_BACK  = np.eye(3, dtype=np.float64)   # placeholder
D_BACK  = np.zeros((1, 5), dtype=np.float64)

K_FRONT = np.eye(3, dtype=np.float64)   # placeholder
D_FRONT = np.zeros((1, 5), dtype=np.float64)

OUT_DIR = "./2_1_camera/plots"

# ─────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────
COLORS = {
    "back":        "#2196F3",   # blue
    "front":       "#FF5722",   # orange
    "detected":    "#4CAF50",   # green
    "reprojected": "#F44336",   # red
    "world":       "#9C27B0",   # purple
    "grid":        "#E0E0E0",
    "bg":          "#FAFAFA",
}
plt.rcParams.update({
    "font.family":      "monospace",
    "axes.facecolor":   COLORS["bg"],
    "figure.facecolor": "white",
    "axes.grid":        True,
    "grid.color":       COLORS["grid"],
    "grid.linewidth":   0.6,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})


# ─────────────────────────────────────────────
# LOAD CSV
# ─────────────────────────────────────────────
def load_csv(path):
    df = pd.read_csv(path)
    df = df.dropna(subset=["xi", "yi", "xw", "yw"])
    df[["xi", "yi", "xw", "yw"]] = df[["xi", "yi", "xw", "yw"]].astype(float)
    return df


# ─────────────────────────────────────────────
# SOLVE PnP  →  rvec, tvec
# ─────────────────────────────────────────────
def solve_pnp(df, K, D):
    obj_pts = df[["xw", "yw"]].values
    obj_pts = np.column_stack([obj_pts, np.zeros(len(obj_pts))]).astype(np.float32)
    img_pts = df[["xi", "yi"]].values.astype(np.float32)

    ok, rvec, tvec = cv2.solvePnP(
        obj_pts, img_pts, K, D,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        raise RuntimeError("solvePnP failed")
    return rvec, tvec


# ─────────────────────────────────────────────
# REPROJECT
# ─────────────────────────────────────────────
def reproject(df, K, D, rvec, tvec):
    obj_pts = df[["xw", "yw"]].values
    obj_pts = np.column_stack([obj_pts, np.zeros(len(obj_pts))]).astype(np.float32)
    proj, _ = cv2.projectPoints(obj_pts, rvec, tvec, K, D)
    return proj.reshape(-1, 2)


# ─────────────────────────────────────────────
# PLOT 1 – World XY board layout
# ─────────────────────────────────────────────
def plot_world_layout(ax, df, color, label):
    pts = df[["xw", "yw"]].drop_duplicates().values
    ax.scatter(pts[:, 1], pts[:, 0],
               s=60, color=color, alpha=0.85,
               edgecolors="white", linewidths=0.6, label=label, zorder=3)

    # draw grid lines between consecutive cols / rows
    nc, nr = CHESSBOARD_SIZE
    grid = pts.reshape(nr, nc, 2)
    for r in range(nr):
        ax.plot(grid[r, :, 1], grid[r, :, 0], color=color, alpha=0.25, lw=0.8)
    for c in range(nc):
        ax.plot(grid[:, c, 1], grid[:, c, 0], color=color, alpha=0.25, lw=0.8)

    # mark anchor (index 0)
    ax.scatter(pts[0, 1], pts[0, 0],
               s=120, color=color, marker="*", zorder=5, label=f"{label} anchor")

    ax.set_xlabel("Yw  (mm)")
    ax.set_ylabel("Xw  (mm)")
    ax.set_aspect("equal")
    ax.invert_yaxis()


# ─────────────────────────────────────────────
# PLOT 2 – Detected vs Reprojected image points
# ─────────────────────────────────────────────
def plot_image_points(ax, df, reproj, color, label):
    det = df[["xi", "yi"]].values

    ax.scatter(det[:, 0], det[:, 1],
               s=28, color=COLORS["detected"], alpha=0.8,
               label="Detected", zorder=3)
    ax.scatter(reproj[:, 0], reproj[:, 1],
               s=28, color=COLORS["reprojected"], marker="x",
               linewidths=1.2, alpha=0.9, label="Reprojected", zorder=4)

    # connector lines
    for d, r in zip(det, reproj):
        ax.plot([d[0], r[0]], [d[1], r[1]],
                color="gray", alpha=0.25, lw=0.6)

    ax.set_xlabel("u  (px)")
    ax.set_ylabel("v  (px)")
    ax.invert_yaxis()
    ax.set_title(f"{label} – Image Points", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right")


# ─────────────────────────────────────────────
# PLOT 3 – Reprojection error per point
# ─────────────────────────────────────────────
def plot_reprojection_error(ax, df, reproj, color, label):
    det    = df[["xi", "yi"]].values
    errors = np.linalg.norm(reproj - det, axis=1)
    mean_e = errors.mean()
    rms_e  = np.sqrt((errors ** 2).mean())

    x = np.arange(len(errors))
    ax.bar(x, errors, color=color, alpha=0.65, width=0.8)
    ax.axhline(mean_e, color="black",  lw=1.2, ls="--", label=f"Mean {mean_e:.3f} px")
    ax.axhline(rms_e,  color="dimgray", lw=1.0, ls=":",  label=f"RMS  {rms_e:.3f} px")

    ax.set_xlabel("Point index")
    ax.set_ylabel("Error  (px)")
    ax.set_title(f"{label} – Reprojection Error", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7)
    return mean_e, rms_e


# ─────────────────────────────────────────────
# PLOT 4 – Error scatter (u_err vs v_err)
# ─────────────────────────────────────────────
def plot_error_scatter(ax, df, reproj, color, label):
    det   = df[["xi", "yi"]].values
    delta = reproj - det          # (N, 2)

    ax.scatter(delta[:, 0], delta[:, 1],
               s=24, color=color, alpha=0.7, edgecolors="white", lw=0.4)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="black", lw=0.8)

    # 1-px circle
    theta = np.linspace(0, 2 * np.pi, 200)
    ax.plot(np.cos(theta), np.sin(theta),
            color="tomato", lw=1.0, ls="--", alpha=0.7, label="1 px")

    ax.set_xlabel("Δu  (px)")
    ax.set_ylabel("Δv  (px)")
    ax.set_aspect("equal")
    ax.set_title(f"{label} – Error Scatter", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7)


# ─────────────────────────────────────────────
# BUILD FULL FIGURE
# ─────────────────────────────────────────────
def build_figure(cam_label, df, K, D, color):
    rvec, tvec = solve_pnp(df, K, D)
    reproj     = reproject(df, K, D, rvec, tvec)

    fig = plt.figure(figsize=(16, 11))
    fig.suptitle(f"Extrinsic Calibration  –  {cam_label}", fontsize=13, fontweight="bold", y=0.98)

    gs = gridspec.GridSpec(2, 3, figure=fig,
                           hspace=0.38, wspace=0.32,
                           left=0.07, right=0.97, top=0.93, bottom=0.07)

    # ── World layout  (spans left column both rows)
    ax_world = fig.add_subplot(gs[:, 0])
    plot_world_layout(ax_world, df, color, cam_label)
    ax_world.set_title("World Point Layout", fontsize=10, fontweight="bold")
    ax_world.legend(fontsize=7)

    # ── Image points
    ax_img = fig.add_subplot(gs[0, 1])
    plot_image_points(ax_img, df, reproj, color, cam_label)

    # ── Error scatter
    ax_scatter = fig.add_subplot(gs[0, 2])
    plot_error_scatter(ax_scatter, df, reproj, color, cam_label)

    # ── Reprojection error bar
    ax_err = fig.add_subplot(gs[1, 1:])
    mean_e, rms_e = plot_reprojection_error(ax_err, df, reproj, color, cam_label)

    # ── Stats text box
    R, _ = cv2.Rodrigues(rvec)
    t    = tvec.flatten()
    stats = (
        f"Points   : {len(df)}\n"
        f"Mean err : {mean_e:.4f} px\n"
        f"RMS  err : {rms_e:.4f} px\n\n"
        f"rvec  : [{rvec[0,0]:.4f}, {rvec[1,0]:.4f}, {rvec[2,0]:.4f}]\n"
        f"tvec  : [{t[0]:.2f}, {t[1]:.2f}, {t[2]:.2f}] mm\n\n"
        f"R:\n"
        f"  [{R[0,0]:.4f}  {R[0,1]:.4f}  {R[0,2]:.4f}]\n"
        f"  [{R[1,0]:.4f}  {R[1,1]:.4f}  {R[1,2]:.4f}]\n"
        f"  [{R[2,0]:.4f}  {R[2,1]:.4f}  {R[2,2]:.4f}]"
    )
    fig.text(0.07, 0.01, stats, fontsize=7.5,
             verticalalignment="bottom",
             fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.4", fc="#F5F5F5", ec="#BDBDBD", lw=0.8))

    return fig, rvec, tvec


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    cameras = [
        ("Camera 2 – BACK",  CSV_BACK,  K_BACK,  D_BACK,  COLORS["back"]),
        ("Camera 4 – FRONT", CSV_FRONT, K_FRONT, D_FRONT, COLORS["front"]),
    ]

    for label, csv_path, K, D, color in cameras:
        print(f"\n{'─'*50}")
        print(f"  {label}")
        print(f"{'─'*50}")

        if not os.path.exists(csv_path):
            print(f"  ⚠  CSV not found: {csv_path}  →  skipping")
            continue

        df = load_csv(csv_path)
        if df.empty:
            print("  ⚠  No valid points in CSV  →  skipping")
            continue

        print(f"  Loaded {len(df)} points from {csv_path}")

        try:
            fig, rvec, tvec = build_figure(label, df, K, D, color)
        except RuntimeError as e:
            print(f"  ✗  {e}")
            continue

        safe = label.replace(" ", "_").replace("–", "").replace("/", "")
        out  = os.path.join(OUT_DIR, f"extrinsic_{safe}.png")
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"  ✓  Saved → {out}")
        plt.show()

    print("\nAll done.")


if __name__ == "__main__":
    main()
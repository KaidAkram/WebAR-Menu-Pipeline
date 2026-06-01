"""
========================================================================
 GLOMAP Post-Run Analyzer — Metrics, Visualizations & Report
========================================================================
 Run this on WINDOWS after all GLOMAP dishes complete.
 It reads sparse models + metrics, generates per-dish charts,
 cross-dish comparisons, and a comprehensive Markdown report.

 Usage:
   python analyze_glomap.py
   python analyze_glomap.py --outputs_dir D:/custom/path/outputs
========================================================================
"""

import os
import sys
import json
import struct
import argparse
import numpy as np
from datetime import datetime

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("[WARN] matplotlib not found. Install with: pip install matplotlib")
    print("       Visualizations will be skipped.\n")


# ======================================================================
#  COLMAP Binary Readers
# ======================================================================

CAMERA_MODEL_NUM_PARAMS = {
    0: 3,   # SIMPLE_PINHOLE
    1: 4,   # PINHOLE
    2: 4,   # SIMPLE_RADIAL
    3: 5,   # RADIAL
    4: 8,   # OPENCV
    5: 8,   # OPENCV_FISHEYE
    6: 12,  # FULL_OPENCV
    7: 5,   # FOV
    8: 4,   # SIMPLE_RADIAL_FISHEYE
    9: 5,   # RADIAL_FISHEYE
    10: 12, # THIN_PRISM_FISHEYE
}

CAMERA_MODEL_NAMES = {
    0: "SIMPLE_PINHOLE", 1: "PINHOLE", 2: "SIMPLE_RADIAL",
    3: "RADIAL", 4: "OPENCV", 5: "OPENCV_FISHEYE",
    6: "FULL_OPENCV", 7: "FOV", 8: "SIMPLE_RADIAL_FISHEYE",
    9: "RADIAL_FISHEYE", 10: "THIN_PRISM_FISHEYE",
}


def read_cameras_binary(path):
    """Read cameras.bin from COLMAP sparse model."""
    cameras = {}
    with open(path, "rb") as f:
        num_cameras = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_cameras):
            camera_id = struct.unpack("<I", f.read(4))[0]
            model_id = struct.unpack("<i", f.read(4))[0]
            width = struct.unpack("<Q", f.read(8))[0]
            height = struct.unpack("<Q", f.read(8))[0]
            num_params = CAMERA_MODEL_NUM_PARAMS.get(model_id, 4)
            params = struct.unpack(f"<{num_params}d", f.read(8 * num_params))
            cameras[camera_id] = {
                "model_id": model_id,
                "model_name": CAMERA_MODEL_NAMES.get(model_id, "UNKNOWN"),
                "width": width,
                "height": height,
                "params": list(params),
            }
    return cameras


def read_images_binary(path):
    """Read images.bin from COLMAP sparse model."""
    images = {}
    with open(path, "rb") as f:
        num_images = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_images):
            image_id = struct.unpack("<I", f.read(4))[0]
            qw, qx, qy, qz = struct.unpack("<4d", f.read(32))
            tx, ty, tz = struct.unpack("<3d", f.read(24))
            camera_id = struct.unpack("<I", f.read(4))[0]

            # Read null-terminated name
            name_bytes = b""
            while True:
                ch = f.read(1)
                if ch == b"\x00":
                    break
                name_bytes += ch
            name = name_bytes.decode("utf-8")

            # Read 2D points
            num_points2D = struct.unpack("<Q", f.read(8))[0]
            points2D = []
            num_matched = 0
            for _ in range(num_points2D):
                x, y = struct.unpack("<2d", f.read(16))
                point3D_id = struct.unpack("<q", f.read(8))[0]
                points2D.append((x, y, point3D_id))
                if point3D_id >= 0:
                    num_matched += 1

            images[image_id] = {
                "qvec": (qw, qx, qy, qz),
                "tvec": (tx, ty, tz),
                "camera_id": camera_id,
                "name": name,
                "num_points2D": num_points2D,
                "num_matched": num_matched,
            }
    return images


def read_points3D_binary(path):
    """Read points3D.bin from COLMAP sparse model."""
    points = {}
    with open(path, "rb") as f:
        num_points = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_points):
            point_id = struct.unpack("<Q", f.read(8))[0]
            x, y, z = struct.unpack("<3d", f.read(24))
            r, g, b = struct.unpack("<3B", f.read(3))
            error = struct.unpack("<d", f.read(8))[0]
            track_length = struct.unpack("<Q", f.read(8))[0]
            # Skip track data (image_id + point2D_idx per element)
            f.read(track_length * 8)
            points[point_id] = {
                "xyz": (x, y, z),
                "rgb": (r, g, b),
                "error": error,
                "track_length": track_length,
            }
    return points


def qvec_to_rotmat(qvec):
    """Convert quaternion to rotation matrix."""
    qw, qx, qy, qz = qvec
    R = np.array([
        [1 - 2*qy*qy - 2*qz*qz, 2*qx*qy - 2*qz*qw,     2*qx*qz + 2*qy*qw],
        [2*qx*qy + 2*qz*qw,     1 - 2*qx*qx - 2*qz*qz,  2*qy*qz - 2*qx*qw],
        [2*qx*qz - 2*qy*qw,     2*qy*qz + 2*qx*qw,       1 - 2*qx*qx - 2*qy*qy],
    ])
    return R


def get_camera_positions(images):
    """Extract camera world positions from images dict."""
    positions = []
    names = []
    for img in images.values():
        R = qvec_to_rotmat(img["qvec"])
        t = np.array(img["tvec"])
        # Camera center in world coords: C = -R^T * t
        C = -R.T @ t
        positions.append(C)
        names.append(img["name"])
    return np.array(positions), names


# ======================================================================
#  Visualization Generators
# ======================================================================

# Consistent style
STYLE = {
    "figure.facecolor": "#1a1a2e",
    "axes.facecolor": "#16213e",
    "axes.edgecolor": "#e0e0e0",
    "axes.labelcolor": "#e0e0e0",
    "text.color": "#e0e0e0",
    "xtick.color": "#e0e0e0",
    "ytick.color": "#e0e0e0",
    "grid.color": "#2a2a4a",
    "grid.alpha": 0.5,
    "font.size": 11,
}


def apply_style():
    plt.rcParams.update(STYLE)
    try:
        plt.rcParams["font.family"] = "sans-serif"
    except Exception:
        pass


def plot_features_per_image(images, save_path, dish_label):
    """Bar chart of features per image."""
    apply_style()
    sorted_imgs = sorted(images.values(), key=lambda x: x["name"])
    names = [img["name"].replace("frame_", "").replace(".jpg", "") for img in sorted_imgs]
    features = [img["num_points2D"] for img in sorted_imgs]
    matched = [img["num_matched"] for img in sorted_imgs]

    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(names))
    ax.bar(x, features, color="#4cc9f0", alpha=0.7, label="Total features")
    ax.bar(x, matched, color="#f72585", alpha=0.7, label="Matched to 3D")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Feature Count")
    ax.set_title(f"Features Per Image — {dish_label}", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(True, axis="y")

    # Show every Nth label
    step = max(1, len(names) // 20)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(names[::step], rotation=45, ha="right", fontsize=8)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_reprojection_error(points, save_path, dish_label):
    """Histogram of per-point reprojection errors."""
    apply_style()
    errors = [p["error"] for p in points.values()]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(errors, bins=80, color="#4cc9f0", alpha=0.8, edgecolor="#1a1a2e")
    mean_err = np.mean(errors)
    median_err = np.median(errors)
    ax.axvline(mean_err, color="#f72585", linestyle="--", linewidth=2, label=f"Mean: {mean_err:.3f}px")
    ax.axvline(median_err, color="#7209b7", linestyle="--", linewidth=2, label=f"Median: {median_err:.3f}px")
    ax.set_xlabel("Reprojection Error (px)")
    ax.set_ylabel("Count")
    ax.set_title(f"Reprojection Error Distribution — {dish_label}", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_track_lengths(points, save_path, dish_label):
    """Histogram of track lengths."""
    apply_style()
    tracks = [p["track_length"] for p in points.values()]

    fig, ax = plt.subplots(figsize=(10, 5))
    max_track = min(max(tracks) if tracks else 1, 30)
    ax.hist(tracks, bins=range(1, max_track + 2), color="#7209b7", alpha=0.8, edgecolor="#1a1a2e")
    mean_track = np.mean(tracks)
    ax.axvline(mean_track, color="#f72585", linestyle="--", linewidth=2, label=f"Mean: {mean_track:.2f}")
    ax.set_xlabel("Track Length (# images seeing this point)")
    ax.set_ylabel("Count")
    ax.set_title(f"Track Length Distribution — {dish_label}", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_camera_positions(images, save_path, dish_label):
    """3D scatter of camera positions — top-down and perspective views."""
    apply_style()
    positions, names = get_camera_positions(images)

    if len(positions) == 0:
        return

    fig = plt.figure(figsize=(14, 6))

    # Top-down view (XZ plane)
    ax1 = fig.add_subplot(1, 2, 1)
    scatter1 = ax1.scatter(positions[:, 0], positions[:, 2],
                           c=np.arange(len(positions)), cmap="plasma",
                           s=15, alpha=0.8)
    ax1.plot(positions[:, 0], positions[:, 2], color="#4cc9f0", alpha=0.3, linewidth=0.5)
    ax1.set_xlabel("X")
    ax1.set_ylabel("Z")
    ax1.set_title("Top-Down View (XZ)", fontsize=12, fontweight="bold")
    ax1.set_aspect("equal")
    ax1.grid(True)

    # 3D perspective
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    ax2.scatter(positions[:, 0], positions[:, 1], positions[:, 2],
                c=np.arange(len(positions)), cmap="plasma", s=10, alpha=0.8)
    ax2.plot(positions[:, 0], positions[:, 1], positions[:, 2],
             color="#4cc9f0", alpha=0.3, linewidth=0.5)
    ax2.set_xlabel("X")
    ax2.set_ylabel("Y")
    ax2.set_zlabel("Z")
    ax2.set_title("3D Camera Trajectory", fontsize=12, fontweight="bold")
    ax2.xaxis.pane.fill = False
    ax2.yaxis.pane.fill = False
    ax2.zaxis.pane.fill = False

    fig.suptitle(f"Camera Positions — {dish_label}", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_comparison_bar(all_metrics, key, ylabel, title, save_path, fmt=".0f"):
    """Bar chart comparing a metric across all dishes."""
    apply_style()
    labels = [f"{m['scenario']}\n{m['dish']}" for m in all_metrics]
    values = [m.get(key, 0) for m in all_metrics]
    colors_dt = ["#4cc9f0", "#4895ef", "#4361ee"]  # Dish_turning shades
    colors_mw = ["#f72585", "#b5179e", "#7209b7"]  # Me_walking shades
    colors = colors_dt + colors_mw

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(range(len(labels)), values, color=colors[:len(labels)], alpha=0.9, edgecolor="#1a1a2e")

    # Add value labels on bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(values)*0.01,
                f"{val:{fmt}}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_timing_breakdown(all_metrics, save_path):
    """Stacked bar chart of timing breakdown per dish."""
    apply_style()
    labels = [f"{m['scenario']}\n{m['dish']}" for m in all_metrics]

    phases = ["feature_extraction_s", "matching_s", "glomap_mapping_s", "copy_images_s"]
    phase_labels = ["Feature Extraction", "Matching", "GLOMAP Mapping", "File Copy"]
    phase_colors = ["#4cc9f0", "#4895ef", "#f72585", "#adb5bd"]

    fig, ax = plt.subplots(figsize=(12, 5))
    bottoms = np.zeros(len(labels))

    for phase, plabel, pcolor in zip(phases, phase_labels, phase_colors):
        values = [m.get("timings", {}).get(phase, 0) for m in all_metrics]
        ax.bar(range(len(labels)), values, bottom=bottoms, color=pcolor, alpha=0.9,
               label=plabel, edgecolor="#1a1a2e")
        bottoms += np.array(values)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Time (seconds)")
    ax.set_title("Timing Breakdown Per Dish", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def plot_summary_table(all_metrics, save_path):
    """Render a formatted summary table as an image."""
    apply_style()

    columns = ["Dish", "Status", "Registered", "3D Points", "Reproj (px)", "Track Len", "Time (s)"]
    rows = []
    row_colors = []

    for m in all_metrics:
        label = f"{m['scenario']}/{m['dish']}"
        status = m.get("status", "?")
        reg = f"{m.get('registered_images', 0)}/{m.get('total_images', 0)}"
        pts = f"{m.get('points_3d', 0):,}"
        reproj = f"{m.get('mean_reprojection_error_px', 0):.3f}"
        track = f"{m.get('mean_track_length', 0):.2f}"
        time_s = f"{m.get('timings', {}).get('total_s', 0)}"
        rows.append([label, status, reg, pts, reproj, track, time_s])

        # Color based on quality
        rate = m.get("registration_rate", 0)
        err = m.get("mean_reprojection_error_px", 99)
        if rate >= 0.95 and err < 0.8:
            row_colors.append("#1b4332")  # green
        elif rate >= 0.85 and err < 1.2:
            row_colors.append("#3a3100")  # yellow
        else:
            row_colors.append("#4a1010")  # red

    fig, ax = plt.subplots(figsize=(14, 2 + len(rows) * 0.6))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=columns,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.8)

    # Style header
    for j, col in enumerate(columns):
        cell = table[0, j]
        cell.set_facecolor("#0f3460")
        cell.set_text_props(color="white", fontweight="bold")

    # Style rows
    for i, color in enumerate(row_colors):
        for j in range(len(columns)):
            cell = table[i + 1, j]
            cell.set_facecolor(color)
            cell.set_text_props(color="white")

    ax.set_title("GLOMAP Results Summary", fontsize=16, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


# ======================================================================
#  Quality Assessment
# ======================================================================

def assess_quality(metrics):
    """Return quality grade and notes for a dish."""
    rate = metrics.get("registration_rate", 0)
    err = metrics.get("mean_reprojection_error_px", 99)
    pts = metrics.get("points_3d", 0)
    status = metrics.get("status", "FAILED")

    if status == "FAILED":
        return "FAILED", "GLOMAP did not produce a sparse model."

    notes = []
    grade = "GOOD"

    if rate >= 0.95:
        notes.append(f"Excellent registration ({rate*100:.1f}%)")
    elif rate >= 0.85:
        notes.append(f"Acceptable registration ({rate*100:.1f}%), some images dropped")
        grade = "OK"
    else:
        notes.append(f"Low registration ({rate*100:.1f}%) — many images failed to register")
        grade = "BAD"

    if err < 0.8:
        notes.append(f"Reprojection error is excellent ({err:.3f}px)")
    elif err < 1.2:
        notes.append(f"Reprojection error is acceptable ({err:.3f}px)")
        if grade == "GOOD":
            grade = "OK"
    else:
        notes.append(f"High reprojection error ({err:.3f}px) — possible calibration issue")
        grade = "BAD"

    if pts < 1000:
        notes.append(f"Very few 3D points ({pts}) — reconstruction may be sparse")
        grade = "BAD"

    return grade, " | ".join(notes)


# ======================================================================
#  Report Generator
# ======================================================================

def generate_report(all_metrics, all_sparse_data, outputs_dir, viz_dir):
    """Generate comprehensive Markdown report."""
    report_path = os.path.join(outputs_dir, "reports", "glomap_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lines = []
    lines.append("# GLOMAP Reconstruction Report")
    lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    # Summary Table
    lines.append("## Summary\n")
    lines.append("| Dish | Status | Grade | Registered | 3D Points | Reproj Error | Track Length | Time |")
    lines.append("|------|--------|-------|------------|-----------|-------------|-------------|------|")

    for m in all_metrics:
        label = f"{m['scenario']}/{m['dish']}"
        grade, _ = assess_quality(m)
        reg = f"{m.get('registered_images',0)}/{m.get('total_images',0)}"
        pts = f"{m.get('points_3d',0):,}"
        err = f"{m.get('mean_reprojection_error_px',0):.3f}px"
        track = f"{m.get('mean_track_length',0):.2f}"
        time_s = m.get("timings", {}).get("total_s", 0)
        time_str = f"{time_s//60}m {time_s%60}s"

        grade_emoji = {"GOOD": "🟢", "OK": "🟡", "BAD": "🔴", "FAILED": "❌"}.get(grade, "❓")
        lines.append(f"| {label} | {m.get('status','?')} | {grade_emoji} {grade} | {reg} | {pts} | {err} | {track} | {time_str} |")

    # Comparison Charts
    lines.append("\n## Cross-Dish Comparison\n")
    comp_dir = os.path.join(viz_dir, "comparison")
    for chart_name, title in [
        ("registered_images.png", "Registration Rate"),
        ("reprojection_errors.png", "Reprojection Errors"),
        ("point_cloud_sizes.png", "Point Cloud Sizes"),
        ("timing_breakdown.png", "Timing Breakdown"),
        ("summary_table.png", "Summary Table"),
    ]:
        chart_path = os.path.join(comp_dir, chart_name)
        if os.path.exists(chart_path):
            lines.append(f"### {title}\n")
            lines.append(f"![{title}]({chart_path.replace(os.sep, '/')})\n")

    # Per-Dish Details
    lines.append("\n## Per-Dish Details\n")
    for m in all_metrics:
        label = f"{m['scenario']}/{m['dish']}"
        dish_viz = os.path.join(viz_dir, f"{m['scenario']}_{m['dish']}")
        grade, notes = assess_quality(m)

        lines.append(f"### {label}\n")
        lines.append(f"**Grade: {grade}** — {notes}\n")

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Registered Images | {m.get('registered_images',0)} / {m.get('total_images',0)} ({m.get('registration_rate',0)*100:.1f}%) |")
        lines.append(f"| 3D Points | {m.get('points_3d',0):,} |")
        lines.append(f"| Observations | {m.get('observations',0):,} |")
        lines.append(f"| Mean Reprojection Error | {m.get('mean_reprojection_error_px',0):.4f} px |")
        lines.append(f"| Mean Track Length | {m.get('mean_track_length',0):.2f} |")
        lines.append(f"| Mean Observations/Image | {m.get('mean_observations_per_image',0):.1f} |")
        lines.append("")

        # Camera info from sparse data
        sparse = all_sparse_data.get(label)
        if sparse and sparse.get("cameras"):
            cam = list(sparse["cameras"].values())[0]
            lines.append(f"**Camera Model:** {cam['model_name']} ({cam['width']}x{cam['height']})\n")

        # Embed visualizations
        for chart_name, chart_title in [
            ("features_per_image.png", "Features Per Image"),
            ("reprojection_error.png", "Reprojection Error Distribution"),
            ("track_length_dist.png", "Track Length Distribution"),
            ("camera_positions.png", "Camera Positions"),
        ]:
            chart_path = os.path.join(dish_viz, chart_name)
            if os.path.exists(chart_path):
                lines.append(f"#### {chart_title}\n")
                lines.append(f"![{chart_title}]({chart_path.replace(os.sep, '/')})\n")

        lines.append("---\n")

    # Recommendations
    lines.append("## Recommendations\n")
    for m in all_metrics:
        label = f"{m['scenario']}/{m['dish']}"
        grade, notes = assess_quality(m)
        if grade == "BAD" or grade == "FAILED":
            lines.append(f"> [!WARNING]\n> **{label}**: {notes}\n")
        elif grade == "OK":
            lines.append(f"> [!NOTE]\n> **{label}**: {notes}\n")

    good_count = sum(1 for m in all_metrics if assess_quality(m)[0] == "GOOD")
    if good_count == len(all_metrics):
        lines.append("> [!TIP]\n> All dishes passed with excellent quality! Ready for 3DGS training.\n")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


# ======================================================================
#  Main Analysis Pipeline
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="GLOMAP Post-Run Analyzer")
    parser.add_argument(
        "--outputs_dir", type=str,
        default=r"D:\glomap_pipeline\glomap_pipeline\outputs",
        help="Path to outputs directory"
    )
    args = parser.parse_args()

    outputs_dir = args.outputs_dir
    viz_dir = os.path.join(outputs_dir, "visualizations")

    print("=" * 65)
    print("  GLOMAP POST-RUN ANALYZER")
    print("=" * 65)

    # ── Collect metrics from all dishes ────────────────────────────
    dishes = [
        ("Dish_turning", "Dish_1"), ("Dish_turning", "Dish_2"), ("Dish_turning", "Dish_3"),
        ("Me_walking", "Dish_1"), ("Me_walking", "Dish_2"), ("Me_walking", "Dish_3"),
    ]

    all_metrics = []
    all_sparse_data = {}

    for scenario, dish in dishes:
        label = f"{scenario}/{dish}"
        dish_dir = os.path.join(outputs_dir, scenario, dish)
        metrics_path = os.path.join(dish_dir, "metrics.json")

        if not os.path.exists(metrics_path):
            print(f"  [SKIP] {label} — no metrics.json found")
            continue

        with open(metrics_path, "r") as f:
            metrics = json.load(f)

        all_metrics.append(metrics)
        print(f"  [OK]   {label} — {metrics.get('registered_images', '?')}/{metrics.get('total_images', '?')} images, "
              f"{metrics.get('points_3d', '?')} points, {metrics.get('mean_reprojection_error_px', '?')}px error")

        # Read sparse model if available
        sparse_dir = os.path.join(dish_dir, "sparse")
        # Check for sparse/0/ or sparse/ directly
        if os.path.exists(os.path.join(sparse_dir, "0", "cameras.bin")):
            sparse_dir = os.path.join(sparse_dir, "0")
        elif not os.path.exists(os.path.join(sparse_dir, "cameras.bin")):
            print(f"         (no sparse model binaries found)")
            continue

        try:
            cameras = read_cameras_binary(os.path.join(sparse_dir, "cameras.bin"))
            images = read_images_binary(os.path.join(sparse_dir, "images.bin"))
            points = read_points3D_binary(os.path.join(sparse_dir, "points3D.bin"))
            all_sparse_data[label] = {
                "cameras": cameras, "images": images, "points": points
            }
            print(f"         Parsed: {len(cameras)} cameras, {len(images)} images, {len(points)} 3D points")
        except Exception as e:
            print(f"         [WARN] Failed to parse sparse model: {e}")

    if not all_metrics:
        print("\n  [ERROR] No metrics found! Did GLOMAP run?")
        sys.exit(1)

    print(f"\n  Loaded {len(all_metrics)} dishes, {len(all_sparse_data)} with sparse models\n")

    # ── Generate Per-Dish Visualizations ──────────────────────────
    if HAS_MPL:
        print("  Generating per-dish visualizations...")
        for label, sparse in all_sparse_data.items():
            scenario, dish = label.split("/")
            dish_viz_dir = os.path.join(viz_dir, f"{scenario}_{dish}")
            os.makedirs(dish_viz_dir, exist_ok=True)

            try:
                plot_features_per_image(
                    sparse["images"],
                    os.path.join(dish_viz_dir, "features_per_image.png"),
                    label
                )
                plot_reprojection_error(
                    sparse["points"],
                    os.path.join(dish_viz_dir, "reprojection_error.png"),
                    label
                )
                plot_track_lengths(
                    sparse["points"],
                    os.path.join(dish_viz_dir, "track_length_dist.png"),
                    label
                )
                plot_camera_positions(
                    sparse["images"],
                    os.path.join(dish_viz_dir, "camera_positions.png"),
                    label
                )
                print(f"    [OK] {label} — 4 charts saved to {dish_viz_dir}")
            except Exception as e:
                print(f"    [ERR] {label} — {e}")

        # ── Generate Comparison Charts ────────────────────────────
        print("\n  Generating comparison charts...")
        comp_dir = os.path.join(viz_dir, "comparison")
        os.makedirs(comp_dir, exist_ok=True)

        try:
            plot_comparison_bar(
                all_metrics, "registered_images", "Registered Images",
                "Registered Images by Dish",
                os.path.join(comp_dir, "registered_images.png")
            )
            plot_comparison_bar(
                all_metrics, "mean_reprojection_error_px", "Error (px)",
                "Mean Reprojection Error by Dish",
                os.path.join(comp_dir, "reprojection_errors.png"),
                fmt=".3f"
            )
            plot_comparison_bar(
                all_metrics, "points_3d", "3D Points",
                "Point Cloud Size by Dish",
                os.path.join(comp_dir, "point_cloud_sizes.png")
            )
            plot_timing_breakdown(
                all_metrics,
                os.path.join(comp_dir, "timing_breakdown.png")
            )
            plot_summary_table(
                all_metrics,
                os.path.join(comp_dir, "summary_table.png")
            )
            print(f"    [OK] 5 comparison charts saved to {comp_dir}")
        except Exception as e:
            print(f"    [ERR] Comparison charts — {e}")

    # ── Generate Report ───────────────────────────────────────────
    print("\n  Generating report...")
    report_path = generate_report(all_metrics, all_sparse_data, outputs_dir, viz_dir)
    print(f"    [OK] Report saved to {report_path}")

    # ── Final Summary ─────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  ANALYSIS COMPLETE")
    print(f"{'=' * 65}")

    for m in all_metrics:
        label = f"{m['scenario']}/{m['dish']}"
        grade, notes = assess_quality(m)
        emoji = {"GOOD": "OK", "OK": "~~", "BAD": "!!", "FAILED": "XX"}.get(grade, "??")
        print(f"  [{emoji}] {label}: {grade} — {notes}")

    print(f"\n  Report: {report_path}")
    print(f"  Charts: {viz_dir}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()

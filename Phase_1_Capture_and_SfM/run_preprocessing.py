"""
========================================================================
 ULTIMATE PREPROCESSING PIPELINE FOR GLOMAP + 3DGS TRAINING
========================================================================

Pipeline:
  Phase 1: Smart extraction -- adaptive interval, targets ~3x candidate frames
  Phase 2: Quality filtering -- combined sharpness + exposure rejection
  Phase 3: Duplicate removal -- histogram + SSIM similarity
  Phase 4: Motion filtering -- optical flow rejects near-static frames
  Phase 5: Coverage-aware selection -- ensures 360 deg viewpoint spread
  Phase 6: Color normalization -- consistent white balance across frames
  Phase 7: Save final clean RGB frames (for GLOMAP)
  Phase 8: (Optional) Background removal -- masks for 3DGS training only

Usage:
  python run_preprocessing.py --video_dir videos/Dish_turning
  python run_preprocessing.py --video_dir videos/Me_turning --target_frames 300
  python run_preprocessing.py --video_dir videos/Dish_turning --skip_bg_removal
"""

import cv2
import os
import sys
import json
import shutil
import numpy as np
from tqdm import tqdm
import argparse
from PIL import Image

# Fix Windows console encoding
# import sys
# if sys.stdout.encoding != 'utf-8':
#     sys.stdout.reconfigure(encoding='utf-8', errors='replace')


try:
    from skimage.metrics import structural_similarity as ssim
    HAS_SSIM = True
except ImportError:
    HAS_SSIM = False
    print("[INFO] scikit-image not found -- using histogram comparison only for duplicates.")
    print("       Install with: pip install scikit-image (recommended)\n")


# ===============================================================================
#  SHARPNESS DETECTION
# ===============================================================================

def laplacian_variance(gray):
    """Classic Laplacian sharpness. Higher = sharper."""
    return cv2.Laplacian(gray, cv2.CV_64F, ksize=3).var()


def tenengrad(gray):
    """Gradient-based sharpness -- more robust for food/object textures."""
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return np.mean(gx ** 2 + gy ** 2)


def sharpness_score(image):
    """Combined sharpness using both metrics for maximum reliability."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap = laplacian_variance(gray)
    ten = tenengrad(gray)
    # Normalize tenengrad to roughly the same scale as laplacian
    return 0.5 * lap + 0.5 * (ten / 100.0)


# ===============================================================================
#  EXPOSURE DETECTION
# ===============================================================================

def exposure_ok(image, low=30, high=220, max_bad_ratio=0.15):
    """
    Reject frames where >15% of pixels are near-black or near-white.
    COLMAP/GLOMAP can't extract reliable SIFT features from uniform regions.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    total = gray.size
    underexposed = np.sum(gray < low) / total
    overexposed = np.sum(gray > high) / total
    return underexposed < max_bad_ratio and overexposed < max_bad_ratio


# ===============================================================================
#  DUPLICATE DETECTION
# ===============================================================================

def histogram_similarity(img1, img2):
    """Fast coarse similarity via colour histogram correlation."""
    h1 = cv2.calcHist([img1], [0, 1, 2], None, [16, 16, 16],
                      [0, 256, 0, 256, 0, 256])
    h2 = cv2.calcHist([img2], [0, 1, 2], None, [16, 16, 16],
                      [0, 256, 0, 256, 0, 256])
    cv2.normalize(h1, h1)
    cv2.normalize(h2, h2)
    return cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)


def ssim_similarity(img1, img2, size=256):
    """Structural similarity -- slower but catches subtle duplicates."""
    if not HAS_SSIM:
        return 0.0
    g1 = cv2.cvtColor(cv2.resize(img1, (size, size)), cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(cv2.resize(img2, (size, size)), cv2.COLOR_BGR2GRAY)
    return ssim(g1, g2, data_range=255)


def are_duplicates(img1, img2, hist_thresh=0.97, ssim_thresh=0.92):
    """
    Two-stage duplicate check:
      1. Fast histogram check -- if below threshold, definitely not a duplicate
      2. Slow SSIM check -- confirms duplicates that passed histogram
    """
    hist_sim = histogram_similarity(img1, img2)
    if HAS_SSIM:
        if hist_sim < hist_thresh:
            return False
        return ssim_similarity(img1, img2) > ssim_thresh
    
    # Without SSIM, be much stricter on histogram similarity
    # A threshold of 0.999 is safer for objects turning where histograms barely change.
    return hist_sim > 0.999


# ===============================================================================
#  MOTION DETECTION (Optical Flow)
# ===============================================================================

def optical_flow_motion(prev_gray, curr_gray):
    """
    Estimate camera motion using sparse optical flow (Lucas-Kanade).
    Returns median displacement in pixels.
    Low motion = camera barely moved = redundant frame for GLOMAP.
    """
    corners = cv2.goodFeaturesToTrack(
        prev_gray, maxCorners=200, qualityLevel=0.01, minDistance=10
    )
    if corners is None or len(corners) < 10:
        return 0.0

    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_gray, curr_gray, corners, None,
        winSize=(21, 21), maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    )

    good_prev = corners[status.flatten() == 1]
    good_curr = curr_pts[status.flatten() == 1]

    if len(good_prev) < 5:
        return 0.0

    displacement = np.linalg.norm(good_curr - good_prev, axis=2)
    return float(np.median(displacement))


# ===============================================================================
#  COLOR NORMALIZATION
# ===============================================================================

def normalize_color(image, target_mean=118.0):
    """
    Normalize brightness to a target mean and apply CLAHE for local contrast.
    Consistent exposure across frames helps SIFT feature matching in GLOMAP.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    current_mean = np.mean(l)
    if current_mean < 1:
        return image
    scale = target_mean / current_mean
    l_norm = np.clip(l * scale, 0, 255).astype(np.uint8)
    # CLAHE for local contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_norm = clahe.apply(l_norm)
    lab_norm = cv2.merge([l_norm, a, b])
    return cv2.cvtColor(lab_norm, cv2.COLOR_LAB2BGR)


# ===============================================================================
#  COVERAGE-AWARE FRAME SELECTION
# ===============================================================================

def select_coverage_frames(frames_data, target_count):
    """
    Select frames that maximise viewpoint coverage rather than just
    picking every Nth frame. Uses cumulative motion as a proxy for
    camera angle -- ensures even distribution around the object.

    frames_data: list of dicts with keys: path, sharpness, motion_accum, original_idx
    """
    if len(frames_data) <= target_count:
        return frames_data

    # Sort by accumulated motion (proxy for camera angle around object)
    sorted_frames = sorted(frames_data, key=lambda f: f['motion_accum'])

    # Divide into equal-size buckets and pick the sharpest from each
    bucket_size = len(sorted_frames) / target_count
    selected = []
    for i in range(target_count):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        bucket = sorted_frames[start:end]
        # Pick sharpest frame in this viewpoint bucket
        best = max(bucket, key=lambda f: f['sharpness'])
        selected.append(best)

    # Re-sort by original order (GLOMAP benefits from temporal ordering)
    selected.sort(key=lambda f: f['original_idx'])
    return selected


# ===============================================================================
#  IMAGE RESIZING
# ===============================================================================

def resize_image(image, max_res):
    """Resize image so the longest side does not exceed max_res."""
    h, w = image.shape[:2]
    if max(h, w) > max_res:
        scale = max_res / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return image


# ===============================================================================
#  MAIN PIPELINE
# ===============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Ultimate Preprocessing Pipeline for GLOMAP + 3DGS Training"
    )
    parser.add_argument(
        "--video_dir", required=True,
        help="Directory containing input videos (e.g. videos/Dish_turning)"
    )
    parser.add_argument(
        "--output_dir", default="processed_data",
        help="Output directory for all results"
    )
    parser.add_argument(
        "--target_frames", type=int, default=300,
        help="Target number of final frames (recommended: 200-300 for objects)"
    )
    parser.add_argument(
        "--max_res", type=int, default=1600,
        help="Maximum image resolution on longest side (default: 1600)"
    )
    parser.add_argument(
        "--blur_threshold", type=float, default=150.0,
        help="Sharpness threshold -- higher = stricter (default: 150)"
    )
    parser.add_argument(
        "--min_motion", type=float, default=1.5,
        help="Minimum optical flow displacement in px to keep a frame (default: 1.5)"
    )
    parser.add_argument(
        "--no_color_norm", action="store_true",
        help="Skip colour normalisation"
    )
    parser.add_argument(
        "--skip_bg_removal", action="store_true",
        help="Skip background removal (useful if you only need frames for GLOMAP)"
    )
    parser.add_argument(
        "--is_turntable", action="store_true",
        help="Apply black background and square center crop to GLOMAP images (required for turntable datasets)"
    )
    args = parser.parse_args()

    # ── Directory setup ───────────────────────────────────────────────────
    base_dir = os.path.dirname(os.path.abspath(__file__))
    video_dir = (
        os.path.join(base_dir, args.video_dir)
        if not os.path.isabs(args.video_dir) else args.video_dir
    )
    output_dir = (
        os.path.join(base_dir, args.output_dir)
        if not os.path.isabs(args.output_dir) else args.output_dir
    )

    # Output directories
    IMAGES_GLOMAP_DIR = os.path.join(output_dir, "images_glomap") # Normalized RGB for GLOMAP
    IMAGES_DIR = os.path.join(output_dir, "images")        # Clean RGB for 3DGS
    MASKS_DIR = os.path.join(output_dir, "masks")          # B&W masks for 3DGS
    RGBA_DIR = os.path.join(output_dir, "images_rgba")     # Masked RGBA for inspection
    FRAMES_FINAL = os.path.join(output_dir, "frames_final")  # Legacy compatibility
    CANDIDATES_DIR = os.path.join(output_dir, "_candidates")  # Temp working dir
    REJECTED_DIR = os.path.join(output_dir, "rejected")    # Rejected frames for review

    for d in [IMAGES_GLOMAP_DIR, IMAGES_DIR, MASKS_DIR, RGBA_DIR, FRAMES_FINAL, CANDIDATES_DIR, REJECTED_DIR]:
        os.makedirs(d, exist_ok=True)

    # ── Discover videos ───────────────────────────────────────────────────
    video_files = sorted([
        f for f in os.listdir(video_dir)
        if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))
    ])
    if not video_files:
        print(f"[ERROR] No video files found in {video_dir}")
        sys.exit(1)

    print(f"\n{'=' * 65}")
    print(f"  GLOMAP + 3DGS PREPROCESSING PIPELINE")
    print(f"{'=' * 65}")
    print(f"  Videos:        {video_dir}")
    print(f"  Output:        {output_dir}")
    print(f"  Target frames: {args.target_frames}")
    print(f"  Max resolution: {args.max_res}px")
    print(f"{'=' * 65}\n")

    # ── Count total frames & compute extraction interval ──────────────────
    total_frames = 0
    video_paths = []
    for vf in video_files:
        vpath = os.path.join(video_dir, vf)
        cap = cv2.VideoCapture(vpath)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"  [V] {vf}: {count} frames, {fps:.1f} FPS, {w}x{h}")
        total_frames += count
        video_paths.append(vpath)
        cap.release()

    # Aim for ~3x target frames before filtering (so we have room to reject)
    budget = args.target_frames * 3
    interval = max(1, total_frames // budget)
    expected_candidates = total_frames // interval
    print(f"\n  Total: {total_frames} frames")
    print(f"  Extraction interval: every {interval} frames → ~{expected_candidates} candidates\n")

    # ======================================================================
    #  PHASE 1: EXTRACT CANDIDATE FRAMES (disk-based, memory-efficient)
    # ======================================================================
    print(">> Phase 1/7 -- Extracting candidate frames from video...")
    candidate_count = 0
    frame_idx_global = 0

    for vpath in video_paths:
        cap = cv2.VideoCapture(vpath)
        local_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if local_idx % interval == 0:
                frame = resize_image(frame, args.max_res)
                fname = f"cand_{candidate_count:05d}.jpg"
                cv2.imwrite(
                    os.path.join(CANDIDATES_DIR, fname),
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 95]
                )
                candidate_count += 1
            local_idx += 1
        cap.release()

    print(f"  → Extracted {candidate_count} candidate frames\n")

    # ======================================================================
    #  PHASE 2: QUALITY FILTERING (sharpness + exposure)
    # ======================================================================
    print(">> Phase 2/7 -- Filtering blur and bad exposure...")
    candidate_files = sorted(os.listdir(CANDIDATES_DIR))
    quality_passed = []  # list of (filename, sharpness_score)
    rejected_blur = 0
    rejected_exp = 0

    for fname in tqdm(candidate_files, desc="  Quality check"):
        fpath = os.path.join(CANDIDATES_DIR, fname)
        img = cv2.imread(fpath)
        if img is None:
            continue

        score = sharpness_score(img)
        if score < args.blur_threshold:
            rejected_blur += 1
            # Move to rejected folder for user review
            shutil.move(fpath, os.path.join(REJECTED_DIR, f"blur_{fname}"))
            continue

        if not exposure_ok(img):
            rejected_exp += 1
            shutil.move(fpath, os.path.join(REJECTED_DIR, f"exp_{fname}"))
            continue

        quality_passed.append((fname, score))

    print(f"  → Passed: {len(quality_passed)} | "
          f"Rejected blur: {rejected_blur} | Rejected exposure: {rejected_exp}\n")

    if len(quality_passed) < 20:
        print(f"  [WARN] Only {len(quality_passed)} frames passed quality check!")
        print(f"         Try lowering --blur_threshold (currently {args.blur_threshold})\n")

    # ======================================================================
    #  PHASE 3: DUPLICATE REMOVAL
    # ======================================================================
    print(">> Phase 3/7 -- Removing duplicate/near-identical frames...")
    unique_frames = []  # list of (filename, score)
    dup_count = 0

    for fname, score in tqdm(quality_passed, desc="  Dedup check"):
        fpath = os.path.join(CANDIDATES_DIR, fname)
        img = cv2.imread(fpath)
        if img is None:
            continue

        is_dup = False
        # Compare against last N unique frames (sliding window)
        for prev_fname, _ in unique_frames[-8:]:
            prev_img = cv2.imread(os.path.join(CANDIDATES_DIR, prev_fname))
            if prev_img is not None and are_duplicates(prev_img, img):
                is_dup = True
                break

        if is_dup:
            dup_count += 1
            shutil.move(fpath, os.path.join(REJECTED_DIR, f"dup_{fname}"))
        else:
            unique_frames.append((fname, score))

    print(f"  → {len(unique_frames)} unique frames (removed {dup_count} duplicates)\n")

    # ======================================================================
    #  PHASE 4: MOTION FILTERING (optical flow)
    # ======================================================================
    print(">> Phase 4/7 -- Filtering low-motion frames (optical flow)...")
    motion_frames = []  # list of dicts
    prev_gray = None
    accum_motion = 0.0
    rejected_motion = 0

    for i, (fname, score) in enumerate(tqdm(unique_frames, desc="  Motion check")):
        fpath = os.path.join(CANDIDATES_DIR, fname)
        img = cv2.imread(fpath)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None:
            motion = optical_flow_motion(prev_gray, gray)
            if motion < args.min_motion:
                rejected_motion += 1
                shutil.move(fpath, os.path.join(REJECTED_DIR, f"static_{fname}"))
                continue
            accum_motion += motion
        else:
            motion = 0.0

        motion_frames.append({
            'filename': fname,
            'sharpness': score,
            'motion_accum': accum_motion,
            'original_idx': i,
        })
        prev_gray = gray

    print(f"  → {len(motion_frames)} frames with sufficient motion "
          f"(removed {rejected_motion} static frames)\n")

    # ======================================================================
    #  PHASE 5: COVERAGE-AWARE FINAL SELECTION
    # ======================================================================
    print(f">> Phase 5/7 -- Selecting {args.target_frames} frames for max 360 deg coverage...")
    selected = select_coverage_frames(motion_frames, args.target_frames)
    print(f"  → Selected {len(selected)} frames with optimal viewpoint spread\n")

    # ======================================================================
    #  PHASE 6: COLOR NORMALIZATION + SAVE FINAL RGB IMAGES
    # ======================================================================
    color_label = "Color normalizing" if not args.no_color_norm else "Saving"
    print(f">> Phase 6/7 -- {color_label} final frames...")
    sharpness_scores = []

    for i, fd in enumerate(tqdm(selected, desc="  Saving")):
        src_path = os.path.join(CANDIDATES_DIR, fd['filename'])
        img = cv2.imread(src_path)
        if img is None:
            continue

        frame_name = f"frame_{i:04d}.jpg"
        
        # Save unmodified original for 3DGS
        cv2.imwrite(os.path.join(IMAGES_DIR, frame_name), img, [cv2.IMWRITE_JPEG_QUALITY, 98])

        # Save normalized version for GLOMAP
        if not args.no_color_norm:
            img_glomap = normalize_color(img)
        else:
            img_glomap = img

        cv2.imwrite(os.path.join(IMAGES_GLOMAP_DIR, frame_name), img_glomap, [cv2.IMWRITE_JPEG_QUALITY, 98])
        sharpness_scores.append(fd['sharpness'])

    final_count = len(sharpness_scores)
    print(f"  → Saved {final_count} final frames to {IMAGES_DIR} and {IMAGES_GLOMAP_DIR}\n")

    # ======================================================================
    #  PHASE 7: BACKGROUND REMOVAL (optional, for 3DGS masks)
    # ======================================================================
    if args.skip_bg_removal:
        print(">> Phase 7/7 -- Skipped (--skip_bg_removal flag set)\n")
    else:
        # Import rembg only when needed (it's heavy)
        try:
            import rembg
            from rembg import remove as rembg_remove
        except ImportError:
            print(">> Phase 7/7 -- SKIPPED: rembg not installed.")
            print("  Install with: pip install rembg onnxruntime")
            print("  You can run this step later.\n")
            rembg_remove = None

        if rembg_remove is not None:
            print(f">> Phase 7/7 -- AI Background Removal on {final_count} frames...")
            print("  (Initializing isnet-general-use model...)\n")
            rembg_session = rembg.new_session("isnet-general-use")

            final_images = sorted(os.listdir(IMAGES_DIR))
            for fname in tqdm(final_images, desc="  BG removal"):
                img_path = os.path.join(IMAGES_DIR, fname)
                img_path_glomap = os.path.join(IMAGES_GLOMAP_DIR, fname)
                image_pil = Image.open(img_path)

                # Remove background -> RGBA with transparent bg
                output_pil = rembg_remove(image_pil, session=rembg_session)

                # Save RGBA
                png_name = os.path.splitext(fname)[0] + ".png"
                output_pil.save(os.path.join(RGBA_DIR, png_name))
                output_pil.save(os.path.join(FRAMES_FINAL, png_name))

                # Extract alpha channel as B&W mask
                output_np = np.array(output_pil)
                alpha = output_np[:, :, 3]
                cv2.imwrite(os.path.join(MASKS_DIR, png_name), alpha)

                if args.is_turntable:
                    # Create solid black background
                    black_bg = Image.new("RGBA", output_pil.size, (0, 0, 0, 255))
                    composited = Image.alpha_composite(black_bg, output_pil)
                    
                    # Square center crop
                    width, height = composited.size
                    new_size = min(width, height)
                    left = (width - new_size) // 2
                    top = (height - new_size) // 2
                    right = (width + new_size) // 2
                    bottom = (height + new_size) // 2
                    crop_box = (left, top, right, bottom)
                    
                    cropped = composited.crop(crop_box)
                    
                    # Overwrite the unmasked RGB frame for 3DGS
                    cropped.convert("RGB").save(img_path)

                    # For GLOMAP image (which has CLAHE), we must also apply the mask, black bg, and crop
                    image_glomap_pil = Image.open(img_path_glomap)
                    image_glomap_rgba = image_glomap_pil.convert("RGBA")
                    image_glomap_rgba.putalpha(Image.fromarray(alpha))
                    glomap_composited = Image.alpha_composite(black_bg, image_glomap_rgba)
                    glomap_cropped = glomap_composited.crop(crop_box)
                    glomap_cropped.convert("RGB").save(img_path_glomap)
                    
                    # Also crop the mask to match the RGB image dimensions
                    mask_pil = Image.fromarray(alpha)
                    mask_cropped = mask_pil.crop(crop_box)
                    cv2.imwrite(os.path.join(MASKS_DIR, png_name), np.array(mask_cropped))

            print(f"  → Masks saved to {MASKS_DIR}\n")

    # ── Cleanup temp candidates ───────────────────────────────────────────
    shutil.rmtree(CANDIDATES_DIR, ignore_errors=True)

    # ── Save run config for reproducibility ───────────────────────────────
    config = vars(args).copy()
    config['total_video_frames'] = total_frames
    config['candidates_extracted'] = candidate_count
    config['final_frame_count'] = final_count
    if sharpness_scores:
        config['sharpness_min'] = float(np.min(sharpness_scores))
        config['sharpness_avg'] = float(np.mean(sharpness_scores))
        config['sharpness_max'] = float(np.max(sharpness_scores))
    config['rejected'] = {
        'blur': rejected_blur,
        'exposure': rejected_exp,
        'duplicates': dup_count,
        'low_motion': rejected_motion,
    }

    config_path = os.path.join(output_dir, "preprocess_config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # ======================================================================
    #  SUMMARY REPORT
    # ======================================================================
    print(f"{'=' * 65}")
    print(f"  [OK] PREPROCESSING COMPLETE")
    print(f"{'=' * 65}")
    print()
    print(f"  [*] Pipeline Statistics:")
    print(f"     Total video frames:    {total_frames}")
    print(f"     Candidates extracted:  {candidate_count}")
    print(f"     Rejected (blur):       {rejected_blur}")
    print(f"     Rejected (exposure):   {rejected_exp}")
    print(f"     Rejected (duplicates): {dup_count}")
    print(f"     Rejected (no motion):  {rejected_motion}")
    print(f"     Final frames:          {final_count}")
    if sharpness_scores:
        print(f"     Sharpness: min={np.min(sharpness_scores):.1f}  "
              f"avg={np.mean(sharpness_scores):.1f}  "
              f"max={np.max(sharpness_scores):.1f}")
    print()
    print(f"  [>] Output Folders:")
    print(f"     images_glomap/ → {final_count} normalized RGB (USE THIS FOR GLOMAP)")
    print(f"     images/        → {final_count} original RGB (USE THIS FOR 3DGS)")
    if not args.skip_bg_removal:
        print(f"     masks/         → {final_count} B&W masks  (USE THIS FOR 3DGS)")
        print(f"     images_rgba/   → {final_count} masked RGBA (for visual check)")
    print(f"     rejected/      → review rejected frames here")
    print(f"     preprocess_config.json → run configuration")
    print()
    print(f"{'=' * 65}")
    print(f"  [!] NEXT STEPS")
    print(f"{'=' * 65}")
    print()
    print(f"  1. Run GLOMAP using the normalized images:")
    print(f"     cp -r \"/mnt/d/glomap_pipeline/glomap_pipeline/processed_data/images_glomap/\"* ~/data/frames_glomap/")
    print(f"     ~/glomap_project/glomap/build/glomap/glomap mapper \\")
    print(f"         --database_path database.db \\")
    print(f"         --image_path ~/data/frames_glomap \\")
    print(f"         --output_path sparse_model")
    print()
    print(f"  2. Run 3DGS using the original images & masks (with the GLOMAP cameras):")
    print(f"     Your 3DGS input should be the 'images/' folder and 'masks/' folder.")
    print()
    print(f"  3. After GLOMAP, use 'masks/' during 3DGS training to")
    print(f"     ignore background. Set splatAlphaRemovalThreshold=20.")
    print()
    print(f"  [!!]  NEVER feed masked/RGBA images to GLOMAP!")
    print(f"      Background features are critical for camera tracking.")
    print()


if __name__ == "__main__":
    main()

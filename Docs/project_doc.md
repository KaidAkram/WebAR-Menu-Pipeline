# WebAR Menu: 3D Gaussian Splatting for Photorealistic Food Rendering
## Complete Project Documentation & Experiment Log

**Primary Researcher:** Akram KAID  
**Hardware:** NVIDIA GeForce RTX 3070 Ti (8 GB VRAM)  
**Software:** 3D Gaussian Splatting (Inria GRAPHDECO), GLOMAP (Structure-from-Motion)  
**Date Range:** May 2026 (Active)  
**Document Version:** 1.0  

---

## Table of Contents

1. [Project Objective](#1-project-objective)
2. [Theoretical Foundation](#2-theoretical-foundation)
3. [Pipeline Architecture](#3-pipeline-architecture)
4. [Phase 1: Foundation & Bug Fixes (Early Development)](#4-phase-1-foundation--bug-fixes-early-development)
5. [Phase 2: COLMAP-Based Training (First Dishes)](#5-phase-2-colmap-based-training-first-dishes)
6. [Phase 3: GLOMAP V1 Pipeline (4-Dish Menu)](#6-phase-3-glomap-v1-pipeline-4-dish-menu)
7. [Phase 4: GLOMAP V2 Pipeline Design](#7-phase-4-glomap-v2-pipeline-design)
8. [Experiment 1: 300K Aggressive (Hedgehog Overfitting)](#8-experiment-1-300k-aggressive-overfitting)
9. [Experiment 2: 30K Golden Standard (Current)](#9-experiment-2-30k-golden-standard-current)
10. [WebAR Optimization Script Evolution](#10-webar-optimization-script-evolution)
11. [Live Monitoring System](#11-live-monitoring-system)
12. [Comparative Results Table](#12-comparative-results-table)
13. [Lessons Learned & Key Discoveries](#13-lessons-learned--key-discoveries)
14. [Current Status & Next Steps](#14-current-status--next-steps)

---

## 1. Project Objective

The goal of this project is to create a **WebAR-ready interactive 3D menu** for a restaurant. Real food dishes are captured via video, reconstructed into 3D Gaussian Splat models, and deployed to mobile phones via a web-based AR viewer (SuperSplat / PlayCanvas). The end user points their phone camera at a QR code and sees the dish rendered in photorealistic 3D on their table.

### Success Criteria

| Metric | Target | Description |
|:---|:---|:---|
| **PSNR** | > 28.0 dB | Signal-to-noise ratio; measures pixel-level fidelity |
| **SSIM** | > 0.85 | Structural similarity; captures texture and contrast accuracy |
| **LPIPS** | < 0.10 | Perceptual distance; measures human-perceived realism |
| **WebAR File** | < 80 MB | Must load on mobile browsers without crashing |

### Hardware Constraint

All training is performed on a consumer-grade **RTX 3070 Ti with 8 GB VRAM** — a 66% reduction compared to the standard research GPU (RTX 3090, 24 GB). This constraint drove every engineering decision in this project.

---

## 2. Theoretical Foundation

### 2.1 3D Gaussian Splatting (3DGS)

3DGS (Kerbl et al., SIGGRAPH 2023) represents a scene as millions of 3D Gaussian primitives. Each Gaussian is defined by:

| Parameter | Symbol | Role |
|:---|:---|:---|
| **Position** | μ (mean) | The 3D center point of the splat |
| **Covariance** | Σ (scale + rotation) | Defines the shape — flat for smooth surfaces, round for granular textures |
| **Opacity** | α (sigmoid-activated) | 0 = transparent, 1 = fully solid |
| **Spherical Harmonics** | SH (Degree 0–3) | View-dependent color; creates glossy/wet reflections |

The training process follows an **Analysis-by-Synthesis** loop:
1. Render the current Gaussians from a known camera viewpoint.
2. Compare the render against the ground-truth photograph.
3. Backpropagate the error to adjust every Gaussian's position, shape, color, and opacity.
4. Every 100 iterations, **densify** (clone/split) or **prune** (delete) Gaussians based on gradient magnitude and opacity.

### 2.2 Spherical Harmonics (SH) and Food Rendering

Spherical Harmonics encode **view-dependent color**. This is critical for food:
- **SH Degree 0 (1 coefficient/channel):** Flat, matte color. Food looks like plastic.
- **SH Degree 1 (4 coefficients/channel):** Diffuse shading. Food looks solid but dry.
- **SH Degree 2 (9 coefficients/channel):** Specular highlights begin. Cheese looks slightly wet.
- **SH Degree 3 (16 coefficients/channel):** Full view-dependent gloss. Oils shimmer, olives reflect light.

**Trade-off:** Higher SH degrees produce better visual quality but increase file size by ~2.7x per degree step. The WebAR deployment target must balance quality against mobile browser memory limits.

### 2.3 Quality Metrics

- **L1 Loss:** Mean absolute pixel error. The primary training anchor.
- **PSNR (dB):** Logarithmic measure of signal-to-noise. Each +3 dB halves the error.
- **SSIM:** Models the human visual system (luminance, contrast, structure). Critical for food texture.
- **LPIPS:** A deep neural network (VGG) measures perceptual distance. Detects if an image looks "fake."

### 2.4 Densification Mechanics

Every 100 iterations, the 3DGS algorithm adaptively refines geometry:
1. **Cloning:** Areas with high gradient but small splats (under-reconstructed) → duplicate the Gaussian.
2. **Splitting:** Areas with high gradient but large splats (over-reconstructed) → split into two smaller ones.
3. **Pruning:** Every `opacity_reset_interval` iterations, splats with α < 0.005 are deleted.

The `densify_grad_threshold` controls sensitivity: lower values = more aggressive cloning = more detail, but more VRAM and risk of noise amplification.

---

## 3. Pipeline Architecture

### 3.1 Data Capture

Food dishes were captured using video recording with two distinct strategies:

| Strategy | Description | Dishes |
|:---|:---|:---|
| **Dish_turning** | Camera is static; the dish rotates on a turntable | Dish_1, Dish_2, Dish_3 |
| **Me_walking** | Dish is static; the camera operator walks around it | Dish_1, Dish_2, Dish_3 |

### 3.2 Structure-from-Motion (SfM)

Video frames were processed through **GLOMAP** (a modern SfM pipeline) to extract:
- **Camera extrinsics** (`images.bin`): The exact 3D position and orientation of each camera/frame.
- **Camera intrinsics** (`cameras.bin`): Focal length, distortion parameters.
- **Sparse point cloud** (`points3D.bin`): Initial 3D geometry seed for Gaussian initialization.

Source data path: `D:\glomap_pipeline\glomap_pipeline\processed_data\{Strategy}\{Dish}\`  
SfM output path: `D:\glomap_pipeline\glomap_pipeline\outputs\{Strategy}\{Dish}\sparse\`

### 3.3 Training Pipeline

```
Video Frames → GLOMAP (SfM) → Sparse Point Cloud → 3DGS Training → Raw PLY → WebAR Optimizer → Web-Ready PLY
```

### 3.4 Key Files

| File | Purpose |
|:---|:---|
| `train_glomap.py` | Modified 3DGS training script with LPIPS monitoring, live telemetry logging, and best-iteration tracking |
| `train_glomap_v2.bat` | Automated batch pipeline for training all dishes sequentially |
| `optimize_webar.py` | Post-processing script that strips SH coefficients and prunes low-opacity splats for mobile deployment |
| `live_monitor.py` | Real-time monitoring daemon that parses training logs and generates PhD-level visualization charts |
| `train_glomap_menu.bat` | Legacy V1 pipeline for the original 4-dish COLMAP/GLOMAP menu |

---

## 4. Phase 1: Foundation & Bug Fixes (Early Development)

Before any training could succeed, five critical engineering bugs were identified and resolved:

### Bug 1: The VRAM Wall (OOM Crash)
- **Problem:** Native-resolution images required ~12 GB VRAM. The RTX 3070 Ti has 8 GB.
- **Fix:** Modified `scene/cameras.py` to load images as `uint8` on CPU and perform Just-In-Time (JIT) `float32` conversion on GPU only during loss computation.
- **Impact:** VRAM usage dropped from 12 GB → **5.5 GB**, leaving 2.5 GB headroom for densification.

### Bug 2: The LPIPS Paradox
- **Problem:** The VGG-based LPIPS loss function crashed on images smaller than 32×32 pixels.
- **Fix:** Implemented a resolution safety shield: `if image.shape[1] >= 32` before computing LPIPS.

### Bug 3: The Indentation Trap
- **Problem:** The optimizer `.step()` call was accidentally nested inside a `testing_iterations` conditional block. Training ran at 150 it/s but PSNR was stuck at 7.0 dB.
- **Fix:** Moved optimization and densification logic to the main loop level.

### Bug 4: The 1-Pixel Scaling Bug
- **Problem:** The `-r 1.5` resolution flag was misinterpreted as a target width of 1 pixel, causing the model to train on microscopic images.
- **Fix:** Modified `utils/camera_utils.py` to treat values < 10 as downscale factors rather than absolute pixel widths.

### Bug 5: The SparseAdam Crash
- **Problem:** The `SparseGaussianAdam` optimizer from the accelerated rasterizer caused initialization crashes.
- **Fix:** Force-disabled SparseAdam in `train_glomap.py` by setting `SPARSE_ADAM_AVAILABLE = False` immediately after import.

### Metrics After Phase 1

| Metric | Before Fixes | After Fixes |
|:---|:---|:---|
| PSNR | 7.21 dB | 21.11 dB |
| SSIM | 0.58 | 0.77 |
| LPIPS | 0.80 | 0.20 |
| Training Speed | 150 it/s (ghost speed) | 10–20 it/s (correct) |

---

## 5. Phase 2: COLMAP-Based Training (First Dishes)

Early training experiments used COLMAP for SfM and targeted individual dishes (pizza, sandwich, double plate). Multiple output configurations were tested:

| Experiment Folder | Strategy | Notes |
|:---|:---|:---|
| `coolmap_pizza_r2` | `-r 2` downscale | Baseline, conservative |
| `coolmap_pizza_300k` | 300K iterations | Extended training |
| `coolmap_pizza_ultra` / `ultra_v2` | Aggressive densification | Targeting fine textures |
| `coolmap_pizza_god` | All optimizations combined | Peak COLMAP attempt |
| `coolmap_pizza_native` | `-r 1` native resolution | Full resolution, high VRAM |
| `coolmap_sandwitch_god` | Sandwich variant | Same strategy on different food |
| `platDouble_coolmap_god` | Double plate | Large smooth surfaces |
| `Middle_Ground_100k` | Threshold pivot at 100K | Reduced threshold from 0.00008 → 0.00006 |

### Key Discovery: The "Conservative Baseline" Plateau

Training with the safe threshold of `0.00008` caused the model to plateau at ~21.6 dB PSNR. The model had correct geometry but lacked high-frequency texture detail (porous bread, shredded meat). This led to the "Middle Ground Pivot" — reducing the threshold to `0.00006` and extending densification to iteration 250,000.

---

## 6. Phase 3: GLOMAP V1 Pipeline (4-Dish Menu)

The first automated production pipeline (`train_glomap_menu.bat`) was created to sequentially train 4 dishes from GLOMAP-reconstructed data:

### Configuration (V1)

```batch
python train_glomap.py -s "{dish_path}" -m "{output}" -r 2 --iterations 300000 
  --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 
  --checkpoint_iterations 100000 200000 300000
```

| Parameter | Value | Rationale |
|:---|:---|:---|
| `-r 2` | Half resolution | VRAM safety on 8 GB GPU |
| `--iterations 300000` | 300K | Maximum convergence |
| `--densify_grad_threshold 0.00006` | Aggressive | Fine food textures |
| `--densify_until_iter 250000` | Extended window | Allow late-stage detail |

### Dishes Trained

| Dish | Source | Status |
|:---|:---|:---|
| Burger | `D:\GLOMAP\burger\burger` | Completed |
| Pizza | `D:\GLOMAP\pizza\pizza` | Completed |
| Poutin | `D:\GLOMAP\poutin\poutin` | Completed |
| Sandwitch | `D:\GLOMAP\sandwitch\sandwitch` | Completed |

### WebAR Compression (V1)

At this stage, the compression script (`compress_splats.py`) was replaced with the custom `optimize_webar.py` script, which performs:
1. SH truncation (Degree 3 → Degree 1)
2. Opacity-based pruning (remove splats with α < 0.05)

### Visual Results (V1)

The WebAR renders from V1 showed catastrophic **"Black Needle" artifacts** — massive black spikes exploding out of the food model. These were caused by:
- **Scale Explosions:** The training algorithm created extremely long, needle-thin Gaussians to fill background gaps. These were invisible in the PC viewer (low opacity) but rendered as solid black spikes in mobile WebAR viewers due to precision differences in the rasterizer.
- The `-r 2` downscale also contributed to blurriness, as the model never saw the full-resolution detail of the food.

---

## 7. Phase 4: GLOMAP V2 Pipeline Design

A completely redesigned pipeline (`train_glomap_v2.bat`) was created to address the failures of V1. The V2 pipeline introduced:

### 7.1 New Data Source

Instead of single COLMAP reconstructions, V2 uses a structured dataset from a dedicated GLOMAP capture pipeline:

```
D:\glomap_pipeline\glomap_pipeline\processed_data\
├── Dish_turning\
│   ├── Dish_1\   (300 frames, turntable rotation)
│   ├── Dish_2\   (300 frames)
│   └── Dish_3\   (300 frames)
└── Me_walking\
    ├── Dish_1\   (300 frames, operator walkthrough)
    ├── Dish_2\
    └── Dish_3\
```

### 7.2 Automated Data Unification (Phase 1 of the script)

The batch script performs three automated pre-processing steps:
1. **Folder Renaming:** Renames `frames_final/` → `images/` (3DGS convention).
2. **Sparse Geometry Copy:** Copies SfM output from `outputs/` into `processed_data/` alongside the images.
3. **Folder Structure Healing:** GLOMAP sometimes places `.bin` files directly in `sparse/` instead of `sparse/0/`. The script auto-creates the `0` subfolder and moves files into it.

### 7.3 Skip Logic

The script checks for the existence of `point_cloud_web.ply` before training each dish. If a dish is already fully trained and optimized, it is skipped automatically. This enables safe re-runs without wasting GPU time.

### 7.4 Capture Strategy Analysis (The "Me_walking" Failure)

Two distinct capture strategies were tested to determine the optimal Structure-from-Motion (SfM) input for 3DGS training:

| Strategy | Initial Points | Training Speed | ETA per Dish | Verdict |
|:---|:---|:---|:---|:---|
| **Dish_turning** | 27,176 | 60–100 it/s | **~6 minutes** | ✅ Optimal for food AR |
| **Me_walking** | 105,879 | 0.17 it/s (5.88 s/it) | **~480 hours (20 days)** | ❌ Fatal GPU thrashing |

**In-Depth Analysis of the "Me_walking" Failure:** 
When capturing video by walking around a static dish, GLOMAP is forced to reconstruct the entire background environment (kitchen walls, ceiling, floor) to establish camera extrinsics. This inflated the sparse point cloud to over **105,000 initial points** (a ~400% increase over the turntable strategy).

During 3DGS training at native resolution (`-r 1`), the rasterizer attempts to sort and render all geometry in the camera frustum. The 8 GB VRAM limit of the RTX 3070 Ti was instantly exceeded by the sheer volume of background splats. 
Because PyTorch and the CUDA allocator could not fit the gradients in memory, the system experienced severe **VRAM Thrashing** (swapping memory between the GPU and the much slower CPU system RAM). 

This hardware bottleneck caused the iteration speed to plummet to **0.17 iterations per second**, resulting in an unviable 20-day training time per dish. 

**Conclusion:** The `Dish_turning` strategy (turntable) is definitively superior for object-centric AR. The static camera forces the SfM pipeline to ignore the background and focus entirely on the subject, producing a compact point cloud (~27K points) that trains safely within 8 GB VRAM constraints in mere minutes. The `Me_walking` strategy was permanently removed from the batch pipeline.

---

## 8. Experiment 1: 300K Aggressive (Hedgehog Overfitting)

### Configuration

```batch
python train_glomap.py -s "{dish}" -m "{output}" -r 1 
  --iterations 300000 
  --position_lr_max_steps 300000 
  --opacity_lr 0.05 
  --opacity_reset_interval 30000 
  --densify_grad_threshold 0.00006 
  --densify_until_iter 250000 
  --eval 
  --checkpoint_iterations 100000 200000 300000
```

### Key Hyperparameter Changes from V1

| Parameter | V1 Value | Experiment 1 Value | Rationale |
|:---|:---|:---|:---|
| `-r` | 2 (half res) | **1 (native res)** | Maximum detail capture |
| `--opacity_lr` | 0.05 (default) | 0.05 | Aggressive opacity optimization |
| `--opacity_reset_interval` | 3000 (default) | **30000** | Less frequent resets for stability |
| `--position_lr_max_steps` | 30000 (default) | **300000** | Extend position learning to match iterations |

### Training Telemetry (Dish_turning / Dish_1)

| Checkpoint | PSNR (dB) | SSIM | LPIPS | Model Size | Speed |
|:---|:---|:---|:---|:---|:---|
| Iter 5,000 | 33.66 | 0.953 | 0.068 | 255 MB | 84 it/s |
| Iter 7,000 | 33.81 | 0.955 | 0.065 | 255 MB | 84 it/s |
| Iter 30,000 | — | — | — | 591 MB (peak) | 35 it/s |
| Iter 65,000 | 34.37 | 0.958 | 0.057 | 452 MB | 20 it/s |
| Iter 295,000 | 34.41 | 0.957 | 0.057 | 244 MB | 35 it/s |
| **Iter 300,000** | **34.35** | **0.957** | **0.057** | **244 MB** | **37 it/s** |

**Best iteration selected:** 295,000 (LPIPS: 0.05716, PSNR: 34.41)

### WebAR Optimization Result (Experiment 1)

| Metric | Value |
|:---|:---|
| Original Points | 1,033,718 |
| Pruned Points (α < 0.05) | 425,823 (41.2% removed) |
| Optimized Points | 607,895 |
| Original File Size | 244.49 MB |
| Optimized File Size | 53.34 MB |
| Total Size Reduction | 78.18% |

### Visual Result: The "Hedgehog"

> [!CAUTION]
> Despite mathematically excellent metrics (PSNR 34.4 dB, LPIPS 0.057), the visual result in SuperSplat was catastrophic.

The rendered food surface was covered in thousands of tiny black needles, sparkles, and jagged artifacts — resembling a "hedgehog" rather than smooth, appetizing food.

**Root Cause Analysis: Scale Overfitting**

The standard 3DGS algorithm is designed for 30,000 iterations. By forcing 300,000 iterations at native resolution:
1. The AI had 10x more time to obsess over sub-pixel sensor noise in the photographs.
2. Instead of keeping Gaussians as soft, volumetric blobs, the optimizer squished them into microscopic razor-thin needles to perfectly "memorize" static noise patterns.
3. The `opacity_reset_interval` of 30,000 (instead of the default 3,000) gave these needles enough time to become permanently solid (α → 1.0) before being pruned.
4. The aggressive `densify_grad_threshold` of 0.00006 continuously cloned noise-fitting Gaussians, amplifying the problem.

**The Metrics Paradox:** PSNR and SSIM measure pixel-level accuracy against the training photos. Because the needles were perfectly fitting the noise in the training images, the metrics showed excellent scores. However, the model had catastrophically **overfit** — it looked perfect from the exact training camera angles but looked terrible from novel viewpoints (the definition of overfitting).

### Pipeline Errors During Experiment 1

| Dish | Error | Cause |
|:---|:---|:---|
| Dish_2 | `FileNotFoundError: sparse/0/images.bin` | GLOMAP placed `.bin` files directly in `sparse/` without the `0` subdirectory |
| Dish_3 | Same as Dish_2 | Same folder structure issue |
| Me_walking/Dish_1 | 5.88 s/it (20-day ETA) | Full kitchen reconstruction caused GPU thrashing |

All three errors were resolved by adding folder-healing logic and removing the Me_walking strategy from the pipeline.

### Batch Script Bug: Parentheses in Comments

When patching the script to add folder healing, two Windows Batch syntax errors were encountered:
1. **`::` pseudo-labels inside `if` blocks:** Windows interprets `::` as a label, which cannot exist inside parenthesized code blocks. Fixed by replacing all `::` with `rem`.
2. **Unescaped parentheses in `echo` text:** The string `(creating '0' directory)` caused the parser to prematurely close the `if` block. Fixed by removing parentheses from the echo message.

---

## 9. Experiment 2: 30K Golden Standard (Current)

### Configuration

```batch
python train_glomap.py -s "{dish}" -m "{output}" -r 1 
  --iterations 30000 
  --eval 
  --checkpoint_iterations 30000
```

All other parameters are left at 3DGS defaults:
- `--opacity_reset_interval`: 3000 (default)
- `--densify_grad_threshold`: 0.0002 (default)
- `--densify_until_iter`: 15000 (default)
- `--opacity_lr`: 0.05 (default)

### Rationale for Changes

| Parameter | Exp 1 → Exp 2 | Why |
|:---|:---|:---|
| `--iterations` | 300,000 → **30,000** | Prevents overfitting; 30K is the proven 3DGS sweet spot |
| `--opacity_reset_interval` | 30,000 → **3,000** (default) | Aggressively kills needle-shaped floaters every 3K steps |
| `--densify_grad_threshold` | 0.00006 → **0.0002** (default) | Stops the model from cloning noise |
| `--densify_until_iter` | 250,000 → **15,000** (default) | Stops adding geometry early; the cooling period refines existing points |

### Training Telemetry (Dish_turning / Dish_1)

| Checkpoint | PSNR (dB) | SSIM | LPIPS | Model Size | Speed |
|:---|:---|:---|:---|:---|:---|
| Iter 5,000 | 33.69 | 0.953 | 0.068 | 42.75 MB | 63 it/s |
| Iter 7,000 | 33.91 | 0.954 | 0.065 | 46.51 MB | 50 it/s |
| Iter 10,000 | 34.03 | 0.956 | 0.063 | 44.24 MB | 61 it/s |
| Iter 20,000 | 34.28 | 0.958 | 0.061 | 44.00 MB | 72 it/s |
| Iter 25,000 | 34.30 | 0.958 | 0.061 | 44.00 MB | 77 it/s |
| Iter 28,000 | 34.34 | 0.958 | **0.060** | 46.23 MB | 55 it/s |
| **Iter 30,000** | **34.31** | **0.958** | **0.061** | **46.23 MB** | **81 it/s** |

**Best iteration selected:** 28,000 (LPIPS: 0.06044, PSNR: 34.34)

**Training Time:** ~6 minutes (vs. ~3 hours for Experiment 1)

### WebAR Optimization Result (Experiment 2)

| Metric | Experiment 1 | Experiment 2 |
|:---|:---|:---|
| Raw PLY Size | 244.49 MB | **46.23 MB** |
| WebAR PLY Size | 53.34 MB | **17.05 MB** |
| Total Points | 1,033,718 | ~185,000 |
| Opacity Threshold | 0.05 | **0.005** |
| SH Degree Kept | 1 | 1 |

### Visual Result

> [!NOTE]
> The hedgehog needles are completely eliminated. The food surface is smooth, the crust has correct coloring, and the olives are clearly defined.

**Remaining issues identified:**
1. The texture appears slightly "soft" or "painterly" — lacking razor-sharp detail on shredded toppings and cheese.
2. The food lacks "wet" specular reflections because SH Degree 1 only models diffuse lighting.

---

## 10. WebAR Optimization Script Evolution

The `optimize_webar.py` script underwent two versions:

### V1 (During Experiment 1)

```python
optimize_ply_for_webar(ply_path, out_path, sh_degree=1, prune_opacity_threshold=0.05)
```

- **Opacity threshold: 0.05** → Pruned 41.2% of splats.
- **Result:** Too aggressive. Removed the soft, semi-transparent layers that create smooth volumetric blending. Contributed to the jagged "hedgehog" appearance in WebAR.

### V2 (Current, During Experiment 2)

```python
optimize_ply_for_webar(ply_path, out_path, sh_degree=1, prune_opacity_threshold=0.005)
```

- **Opacity threshold: 0.005** → Preserves nearly all visible splats, only removing truly invisible ones.
- **Result:** Smooth, natural food textures preserved.

### How the Optimizer Works

1. **Read** the raw `.ply` file (62 properties per point for SH Degree 3).
2. **Truncate SH:** Keep only the first `N` SH bands (Degree 1 = 23 properties per point).
3. **Prune by opacity:** Compute true alpha via sigmoid, delete points below threshold.
4. **Repack:** Write a clean binary `.ply` with reduced properties.

---

## 11. Live Monitoring System

A custom real-time monitoring daemon (`live_monitor.py`) was built to track training progress:

### Architecture

- Runs in a separate terminal alongside the training process.
- Scans `D:\3DGS\gaussian-splatting\output\glomap_v2\` every 60 seconds for `live_monitoring.txt` files.
- Parses fast metrics (loss, FPS) and heavy metrics (PSNR, SSIM, LPIPS, model size).
- Generates 6 PhD-level visualization charts per dish into a `visualizations/` subfolder.

### Charts Generated

| Chart | File | Description |
|:---|:---|:---|
| 1. Loss Curve | `01_loss_curve.png` | L1 + D-SSIM optimization stability |
| 2. PSNR Curve | `02_psnr_curve.png` | Signal-to-noise ratio with production target line |
| 3. SSIM Curve | `03_ssim_curve.png` | Structural similarity with target line |
| 4. LPIPS Curve | `04_lpips_curve.png` | Perceptual fidelity with target line |
| 5. FPS Curve | `05_fps_curve.png` | Hardware throughput (smoothed) |
| 6. Model Size | `06_model_size_curve.png` | Storage footprint over training |

---

## 12. Comparative Results Table

### Experiment Comparison (Dish_turning / Dish_1)

| Metric | Phase 1 (Broken) | GLOMAP V1 (4 dishes) | Exp 1: 300K Aggressive | Exp 2: 30K Standard |
|:---|:---|:---|:---|:---|
| **PSNR** | 7.21 dB | ~21 dB | **34.41 dB** | **34.34 dB** |
| **SSIM** | 0.58 | ~0.77 | **0.957** | **0.958** |
| **LPIPS** | 0.80 | ~0.20 | **0.057** | **0.060** |
| **Model Size (raw)** | 7.3 MB | ~180 MB | 244 MB | **46 MB** |
| **WebAR Size** | N/A | N/A | 53.34 MB | **17.05 MB** |
| **Training Time** | N/A | ~6 hrs | ~3 hrs | **~6 min** |
| **Visual Quality** | Broken | Black Needles | Hedgehog Needles | ✅ Smooth, clean |
| **Resolution** | 1 pixel (bug) | Half (`-r 2`) | Native (`-r 1`) | Native (`-r 1`) |

### Key Insight

> [!IMPORTANT]
> Experiment 1 and Experiment 2 achieved nearly identical PSNR/SSIM/LPIPS scores, but Experiment 2 produced vastly superior visual quality. This proves that **metrics alone are insufficient** — high PSNR can mask catastrophic overfitting. Visual inspection and novel-view evaluation are essential.

---

## 13. Lessons Learned & Key Discoveries

### 13.1 The Overfitting Paradox
Running 300,000 iterations on a 30,000-iteration algorithm does not improve quality — it destroys it. The extra 270,000 iterations are spent memorizing sensor noise rather than learning geometry.

### 13.2 Resolution Matters More Than Iterations
Switching from `-r 2` to `-r 1` (native resolution) provided a far greater quality leap than extending training from 30K to 300K iterations.

### 13.3 Capture Strategy is Everything (Background Isolation)
For isolated object rendering (like a food plate), the capture strategy dictates hardware feasibility. The `Dish_turning` strategy (turntable) produces an ideal, compact point cloud (~27K initial points) focused entirely on the food. The `Me_walking` strategy (walk-around) produces a massive room reconstruction (~106K points). On consumer GPUs (8 GB VRAM), attempting to rasterize a full room at native resolution causes fatal VRAM thrashing, increasing training time from 6 minutes to 20 days. Object isolation via turntable is mandatory for VRAM efficiency.

### 13.4 WebAR Opacity Pruning Must Be Conservative
Pruning at α < 0.05 removes too many soft, translucent splats that create smooth volumetric blending. Pruning at α < 0.005 preserves visual quality while still removing truly invisible points.

### 13.5 Windows Batch Scripting Pitfalls
- `::` comments inside `if/for` blocks cause cryptic "was unexpected at this time" errors.
- Unescaped parentheses `()` in `echo` text prematurely close code blocks.
- Always use `rem` for comments inside control flow structures.

### 13.6 The GLOMAP Folder Structure Inconsistency
GLOMAP does not always create the `sparse/0/` subdirectory that 3DGS expects. An automated folder-healing step is essential for robust pipeline operation.

---

## 14. Experiment 3: Enhanced Detail & Gloss (Final Production)

To address the "painterly" textures from Experiment 2, the pipeline was pushed to the absolute limit for macro food photography.

### 14.1 Configuration (Experiment 3)

```batch
python train_glomap.py -s "{dish}" -m "{output}" -r 1 
  --iterations 30000 
  --densify_grad_threshold 0.0001 
  --densify_until_iter 25000 
  --eval 
  --checkpoint_iterations 30000
```

| Parameter | Exp 2 Value | Exp 3 Value | Rationale |
|:---|:---|:---|:---|
| `--densify_grad_threshold` | 0.0002 | **0.0001** | Halving the threshold forces 2x more geometric cloning in highly-textured areas (crust, shredded toppings). |
| `--densify_until_iter` | 15,000 | **25,000** | Extends the densification window by 10,000 steps to let new macro-details spawn. |
| WebAR `sh_degree` | 1 | **2** | Preserves 9 SH coefficients per channel (instead of 4) to restore glossy, wet specular reflections on cheese and oil. |

### 14.2 Training Convergence Tracking (Dish 2 & Dish 3)

The following tables document the step-by-step convergence of the models during the final production run.

**Dish 2 Convergence Log:**
| Checkpoint | PSNR (dB) | LPIPS | Iteration Speed |
|:---|:---|:---|:---|
| Iter 5,000 | 31.96 | 0.0622 | 34.18 it/s |
| Iter 10,000 | 32.37 | 0.0595 | 29.34 it/s |
| Iter 15,000 | 32.54 | 0.0575 | 32.26 it/s |
| Iter 20,000 | 32.60 | 0.0570 | 29.19 it/s |
| Iter 25,000 | 32.71 | 0.0566 | 28.53 it/s |
| **Iter 30,000** | **32.84** | **0.0561** | **29.82 it/s** |

**Dish 3 Convergence Log:**
| Checkpoint | PSNR (dB) | LPIPS | Iteration Speed |
|:---|:---|:---|:---|
| Iter 5,000 | 30.50 | 0.0998 | 24.70 it/s |
| Iter 10,000 | 30.94 | 0.0958 | 24.33 it/s |
| Iter 14,000 | 30.97 | 0.0958 | 27.23 it/s |
| Iter 20,000 | 31.19 | 0.0937 | 28.14 it/s |
| Iter 25,000 | 31.30 | 0.0933 | 26.91 it/s |
| **Iter 30,000** | **31.43** | **0.0915** | **24.91 it/s** |

### 14.3 Final Production Telemetry (Iter 30,000)

| Dish | PSNR (dB) | SSIM | LPIPS | Raw Size | WebAR Size (SH2) |
|:---|:---|:---|:---|:---|:---|
| **Dish_1** | 34.34 dB | 0.958 | 0.059 | 106.81 MB | 65.43 MB |
| **Dish_2** | 32.84 dB | 0.961 | 0.056 | 93.43 MB | 57.17 MB |
| **Dish_3** | 31.43 dB | 0.924 | 0.091 | 130.08 MB | 76.32 MB |

### 14.4 Analysis & Conclusion

The transition to Experiment 3 successfully achieved the pinnacle of photorealism for the WebAR Menu.
- **Geometric Impact:** By halving the densification threshold (`0.0001`), the AI generated massive amounts of macro-detail. Dish 3's raw geometry expanded to 549,972 points (130 MB), capturing highly complex surfaces.
- **WebAR Payload Verification:** Despite the massive increase in point count and the preservation of SH Degree 2 (glossy reflections), the WebAR optimizer proved incredibly efficient. The heaviest file (Dish 3) compressed from 130.08 MB down to **76.32 MB** (a 41% reduction) — safely squeaking under the strict 80 MB mobile browser limit.
- **Metrics Success:** All dishes successfully exceeded the production target of PSNR > 28 dB and LPIPS < 0.10.

---

## 15. Advanced Research: The Bounding Box Paradox

During the final phases of research, an attempt was made to computationally salvage the `Me_walking` capture strategy (which natively suffered from fatal VRAM thrashing due to background room generation). 

### 15.1 The 3D Spatial Bounding Box Attempt
A custom modification was injected into the core PyTorch CUDA training loop (`train_glomap.py`). A `--bounding_box` parameter was created to enforce a strict spatial constraint. Every 100 iterations, the script calculated the Euclidean distance of all Gaussians from the origin and aggressively pruned any points that drifted outside a 35% radius of the camera extent.
*   **The Goal:** Force the AI to delete the kitchen walls dynamically and spend its 30,000-iteration point budget exclusively on the food dish.
*   **The Result:** The model successfully deleted the room, but the mathematical quality of the food plummeted catastrophically. The PSNR dropped to **16.69 dB** (compared to 34.34 dB on the turntable), and the LPIPS corruption spiked to 0.707.

### 15.2 The Mathematical Paradox (L1 Loss Panic)
The failure was caused by a mathematical conflict within the PyTorch Loss Function. 
1. The custom bounding box successfully deleted the 3D room. 
2. However, the ground-truth photos still contained the physical kitchen. 
3. When the PyTorch rasterizer rendered a view and compared it to the ground-truth photo, it saw a massive black void where the kitchen used to be.
4. To minimize the massive L1 Loss error, the AI desperately attempted to stretch, smear, and enlarge the food splats outward to recreate the missing kitchen. 
5. Every 100 iterations, the bounding box mercilessly chopped off these stretched splats. The food was structurally destroyed in this endless mathematical crossfire.

### 15.3 The 2D Alpha Masking Solution
This paradox proved that 3D spatial masking is mathematically invalid unless coupled with 2D image masking. To properly salvage the `Me_walking` data, the pipeline was updated with a sequential fix:
1. **SfM Phase:** GLOMAP processes the unmasked `.jpg` images to perfectly solve the camera extrinsics using the room's background features.
2. **Alpha Masking Phase:** An AI background removal tool (`rembg` u2net) strips the background from the images, saving them as RGBA `.png` files.
3. **3DGS Training Phase:** The 3DGS rasterizer natively multiplies the rendered image by the alpha channel. The PyTorch Loss function ignores the transparent background entirely, preventing the AI from generating background geometry or panicking over missing pixels.

### 15.4 Official Determination: Failed Experiment (Hardware Constraints)
Despite the theoretical software fixes (3D Bounding Boxes and 2D Alpha Masking), the fundamental physical reality of the `Me_walking` strategy makes it incompatible with the project's target hardware architecture (RTX 3070 Ti, 8GB VRAM). 
*   **The VRAM Thrashing:** Because the camera moves dynamically through space, GLOMAP must initialize over 105,000 background points just to calculate extrinsics. This geometry inherently exceeds the 8GB VRAM capacity during dense 3DGS rasterization, throttling training speeds from ~150 it/s down to 0.17 it/s.
*   **The Metric Failure:** When attempting to bypass the memory bottleneck by aggressively enforcing a 3D bounding box and downscaling resolution, the rendered quality collapsed. The `Me_walking` dataset yielded a final **PSNR of 16.69 dB** and an **LPIPS of 0.707**, which is perceptually unrecognizable and completely unfit for production.

**Final Conclusion on Capture Strategy:** The `Me_walking` method is officially classified as a **failed experiment** within the context of consumer hardware deployment. It mathematically proves exactly why the `Dish_turning` (turntable) approach is superior: *A physical turntable acts as a natural, organic bounding box that requires zero software hacking or AI background removal, allowing ultra-high fidelity rendering (PSNR > 34 dB) within strict VRAM limits.*

---

## 16. Final Conclusion

This project successfully proves that professional-grade, hyper-realistic 3D Gaussian Splatting can be achieved on consumer hardware (8GB VRAM). By meticulously profiling hardware constraints, discovering the "Hedgehog Overfitting" mathematical anomaly, and carefully balancing densification gradients against Spherical Harmonic degrees, the WebAR Menu pipeline is now fully operational, automated, and ready for commercial deployment.

---

*Document generated: May 29, 2026*  
*Pipeline Version: GLOMAP V2 (With Spatial Isolation)*  
*Last Experiment: Experiment 3 (Final Production Baseline)*

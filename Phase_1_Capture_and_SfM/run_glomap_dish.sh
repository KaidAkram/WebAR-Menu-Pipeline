#!/bin/bash
# ================================================================
#  GLOMAP Per-Dish Runner
# ================================================================
#  Usage:  bash run_glomap_dish.sh <scenario> <dish> [gpu_id]
#  Example: bash run_glomap_dish.sh Dish_turning Dish_1 0
# ================================================================

set -euo pipefail

SCENARIO="${1:?Usage: run_glomap_dish.sh <scenario> <dish> [gpu_id]}"
DISH="${2:?Usage: run_glomap_dish.sh <scenario> <dish> [gpu_id]}"
GPU_ID="${3:-0}"

# ── Paths ─────────────────────────────────────────────────────────
WIN_BASE="/mnt/d/glomap_pipeline/glomap_pipeline"
WSL_BASE="/dev/shm/glomap_dishes/${SCENARIO}/${DISH}"
INPUT_IMAGES="${WIN_BASE}/processed_data/${SCENARIO}/${DISH}/images_glomap"
OUTPUT_DIR="${WIN_BASE}/outputs/${SCENARIO}/${DISH}"
LOG_FILE="${OUTPUT_DIR}/glomap_full.log"
METRICS_FILE="${OUTPUT_DIR}/metrics.json"
GLOMAP_BIN="$HOME/glomap_project/glomap/build/glomap/glomap"
DISH_LABEL="${SCENARIO}/${DISH}"

# ── Helper ────────────────────────────────────────────────────────
ts() { date "+%H:%M:%S"; }
log() { echo "[$(ts)] [$DISH_LABEL] $*" | tee -a "$LOG_FILE"; }
separator() { echo "================================================================" | tee -a "$LOG_FILE"; }

# ── Create directories ────────────────────────────────────────────
mkdir -p "$WSL_BASE/images" "$WSL_BASE/sparse" "$OUTPUT_DIR"

# Initialize log
echo "" > "$LOG_FILE"
separator
log "GLOMAP Pipeline Start"
log "  Scenario:  $SCENARIO"
log "  Dish:      $DISH"
log "  GPU:       $GPU_ID"
log "  Input:     $INPUT_IMAGES"
log "  WSL Work:  $WSL_BASE"
log "  Output:    $OUTPUT_DIR"
log "  Started:   $(date)"
separator

# ──────────────────────────────────────────────────────────────────
#  PHASE 1: Copy images to WSL native filesystem (faster I/O)
# ──────────────────────────────────────────────────────────────────
log "PHASE 1/6: Copying images to WSL native filesystem..."
PHASE1_START=$(date +%s)

# Clean previous run if any
rm -rf "$WSL_BASE/images/"* "$WSL_BASE/sparse/"* "$WSL_BASE/database.db" 2>/dev/null || true

cp "${INPUT_IMAGES}/"*.jpg "${WSL_BASE}/images/" 2>/dev/null || \
cp "${INPUT_IMAGES}/"*.png "${WSL_BASE}/images/" 2>/dev/null || \
cp "${INPUT_IMAGES}/"* "${WSL_BASE}/images/"

NUM_IMAGES=$(ls "$WSL_BASE/images/" | wc -l)
PHASE1_END=$(date +%s)
log "PHASE 1 DONE: Copied ${NUM_IMAGES} images in $((PHASE1_END - PHASE1_START))s"

if [ "$NUM_IMAGES" -eq 0 ]; then
    log "ERROR: No images found in $INPUT_IMAGES"
    exit 1
fi

# ──────────────────────────────────────────────────────────────────
#  PHASE 2: COLMAP Feature Extraction (GPU)
# ──────────────────────────────────────────────────────────────────
log "PHASE 2/6: Feature Extraction (GPU=$GPU_ID)..."
PHASE2_START=$(date +%s)

# Prevent Bus Error by deleting corrupted database from previous crashed runs
rm -f "$WSL_BASE/database.db"

# Detect GPU availability
GPU_AVAILABLE=1
if ! command -v nvidia-smi &>/dev/null; then
    GPU_AVAILABLE=0
    log "WARNING: nvidia-smi not found, falling back to CPU"
fi

colmap feature_extractor \
    --database_path "$WSL_BASE/database.db" \
    --image_path "$WSL_BASE/images" \
    --ImageReader.single_camera 1 \
    --FeatureExtraction.num_threads 4 \
    --FeatureExtraction.use_gpu "$GPU_AVAILABLE" \
    --FeatureExtraction.gpu_index "$GPU_ID" \
    --SiftExtraction.max_num_features 8192 \
    2>&1 | tee -a "$LOG_FILE"

PHASE2_END=$(date +%s)
log "PHASE 2 DONE: Feature extraction in $((PHASE2_END - PHASE2_START))s"

# ──────────────────────────────────────────────────────────────────
#  PHASE 3: COLMAP Matching (GPU)
# ──────────────────────────────────────────────────────────────────
log "PHASE 3/6: Feature Matching (GPU=$GPU_ID)..."
PHASE3_START=$(date +%s)

if [ "$SCENARIO" == "Me_walking" ]; then
    log "Using Sequential Matcher (overlap=20) for $SCENARIO to prevent background ghosting..."
    colmap sequential_matcher \
        --database_path "$WSL_BASE/database.db" \
        --SequentialMatching.overlap 20 \
        --SequentialMatching.loop_detection 1 \
        --FeatureMatching.num_threads 4 \
        --FeatureMatching.use_gpu "$GPU_AVAILABLE" \
        --FeatureMatching.gpu_index "$GPU_ID" \
        2>&1 | tee -a "$LOG_FILE"
else
    log "Using Exhaustive Matcher for $SCENARIO..."
    colmap exhaustive_matcher \
        --database_path "$WSL_BASE/database.db" \
        --FeatureMatching.num_threads 4 \
        --FeatureMatching.use_gpu "$GPU_AVAILABLE" \
        --FeatureMatching.gpu_index "$GPU_ID" \
        2>&1 | tee -a "$LOG_FILE"
fi

PHASE3_END=$(date +%s)
log "PHASE 3 DONE: Matching in $((PHASE3_END - PHASE3_START))s"

# ──────────────────────────────────────────────────────────────────
#  PHASE 4: GLOMAP Mapper (CPU)
# ──────────────────────────────────────────────────────────────────
log "PHASE 4/6: GLOMAP Reconstruction..."
PHASE4_START=$(date +%s)

colmap mapper \
    --database_path "$WSL_BASE/database.db" \
    --image_path "$WSL_BASE/images" \
    --output_path "$WSL_BASE/sparse" \
    2>&1 | tee -a "$LOG_FILE"

PHASE4_END=$(date +%s)
log "PHASE 4 DONE: GLOMAP mapping in $((PHASE4_END - PHASE4_START))s"

# ──────────────────────────────────────────────────────────────────
#  PHASE 5: Model Analysis + Metrics Extraction
# ──────────────────────────────────────────────────────────────────
log "PHASE 5/6: Model analysis..."

# Find the sparse model output (could be sparse/0/ or sparse/)
SPARSE_PATH=""
if [ -d "$WSL_BASE/sparse/0" ]; then
    SPARSE_PATH="$WSL_BASE/sparse/0"
elif [ -f "$WSL_BASE/sparse/cameras.bin" ]; then
    SPARSE_PATH="$WSL_BASE/sparse"
else
    log "ERROR: No sparse model found! GLOMAP may have failed."
    log "Contents of sparse/:"
    ls -la "$WSL_BASE/sparse/" 2>&1 | tee -a "$LOG_FILE"

    # Write failure metrics
    TOTAL_TIME=$(( $(date +%s) - PHASE1_START ))
    cat > "$METRICS_FILE" <<FAILEOF
{
    "scenario": "$SCENARIO",
    "dish": "$DISH",
    "status": "FAILED",
    "timestamp": "$(date -Iseconds)",
    "total_images": $NUM_IMAGES,
    "registered_images": 0,
    "registration_rate": 0,
    "points_3d": 0,
    "observations": 0,
    "mean_track_length": 0,
    "mean_observations_per_image": 0,
    "mean_reprojection_error_px": 0,
    "timings": {
        "copy_images_s": $((PHASE1_END - PHASE1_START)),
        "feature_extraction_s": $((PHASE2_END - PHASE2_START)),
        "matching_s": $((PHASE3_END - PHASE3_START)),
        "glomap_mapping_s": $((PHASE4_END - PHASE4_START)),
        "total_s": $TOTAL_TIME
    }
}
FAILEOF
    exit 1
fi

log "Sparse model found at: $SPARSE_PATH"

# Run model analyzer
ANALYZER_OUTPUT=""
ANALYZER_OUTPUT=$(colmap model_analyzer --path "$SPARSE_PATH" 2>&1) || true
echo "$ANALYZER_OUTPUT" | tee -a "$LOG_FILE"

# Clean COLMAP glog prefix (e.g. "I20260528 ... model.cc:456] ") to prevent date parsing bug
CLEAN_OUTPUT=$(echo "$ANALYZER_OUTPUT" | sed 's/.*\] //')

# Parse metrics (flexible patterns for different COLMAP versions)
REGISTERED=$(echo "$CLEAN_OUTPUT" | grep -i "registered" | grep -oP '\d+' | head -1 || echo "0")
POINTS=$(echo "$CLEAN_OUTPUT" | grep -iP "^(Number of )?Points" | grep -oP '\d+' | head -1 || echo "0")
OBSERVATIONS=$(echo "$CLEAN_OUTPUT" | grep -i "observations" | head -1 | grep -oP '\d+' | head -1 || echo "0")
MEAN_TRACK=$(echo "$CLEAN_OUTPUT" | grep -i "mean track" | grep -oP '[\d.]+' | head -1 || echo "0")
MEAN_OBS_IMG=$(echo "$CLEAN_OUTPUT" | grep -i "mean observations per" | grep -oP '[\d.]+' | head -1 || echo "0")
MEAN_REPROJ=$(echo "$CLEAN_OUTPUT" | grep -i "mean reprojection" | grep -oP '[\d.]+' | head -1 || echo "0")

# Fallback defaults
REGISTERED=${REGISTERED:-0}
POINTS=${POINTS:-0}
OBSERVATIONS=${OBSERVATIONS:-0}
MEAN_TRACK=${MEAN_TRACK:-0}
MEAN_OBS_IMG=${MEAN_OBS_IMG:-0}
MEAN_REPROJ=${MEAN_REPROJ:-0}

# Calculate registration rate
REG_RATE=$(awk "BEGIN {printf \"%.4f\", $REGISTERED / $NUM_IMAGES}")

TOTAL_TIME=$(( $(date +%s) - PHASE1_START ))

# Write metrics JSON
cat > "$METRICS_FILE" <<EOF
{
    "scenario": "$SCENARIO",
    "dish": "$DISH",
    "status": "SUCCESS",
    "timestamp": "$(date -Iseconds)",
    "total_images": $NUM_IMAGES,
    "registered_images": $REGISTERED,
    "registration_rate": $REG_RATE,
    "points_3d": $POINTS,
    "observations": $OBSERVATIONS,
    "mean_track_length": $MEAN_TRACK,
    "mean_observations_per_image": $MEAN_OBS_IMG,
    "mean_reprojection_error_px": $MEAN_REPROJ,
    "timings": {
        "copy_images_s": $((PHASE1_END - PHASE1_START)),
        "feature_extraction_s": $((PHASE2_END - PHASE2_START)),
        "matching_s": $((PHASE3_END - PHASE3_START)),
        "glomap_mapping_s": $((PHASE4_END - PHASE4_START)),
        "total_s": $TOTAL_TIME
    }
}
EOF

log "Metrics saved to $METRICS_FILE"

# ──────────────────────────────────────────────────────────────────
#  PHASE 6: Copy Results to Windows
# ──────────────────────────────────────────────────────────────────
log "PHASE 6/6: Copying results to Windows..."
cp -r "$SPARSE_PATH" "$OUTPUT_DIR/sparse/"

separator
log "COMPLETE"
log "  Registered:  $REGISTERED / $NUM_IMAGES images ($REG_RATE)"
log "  3D Points:   $POINTS"
log "  Reproj Err:  ${MEAN_REPROJ}px"
log "  Total Time:  ${TOTAL_TIME}s"
separator

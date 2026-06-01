#!/bin/bash
# ================================================================
#  GLOMAP Master Runner — All 6 Dishes (2 parallel at a time)
# ================================================================
#  Usage (run from WSL):
#    bash /mnt/d/glomap_pipeline/glomap_pipeline/run_glomap_all.sh
#
#  This runs all 6 dishes in 3 groups of 2, sharing the GPU.
#  GPU-bound phases (COLMAP) serialize naturally via CUDA.
#  CPU-bound phases (GLOMAP mapper) run truly in parallel.
# ================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN_BASE="/mnt/d/glomap_pipeline/glomap_pipeline"
MASTER_LOG="${WIN_BASE}/outputs/logs/glomap_master.log"

# Create output directories
mkdir -p "${WIN_BASE}/outputs/logs"
mkdir -p "${WIN_BASE}/outputs/reports"
mkdir -p "${WIN_BASE}/outputs/visualizations/comparison"
for scenario in "Dish_turning" "Me_walking"; do
    for dish in "Dish_1" "Dish_2" "Dish_3"; do
        mkdir -p "${WIN_BASE}/outputs/${scenario}/${dish}"
        mkdir -p "${WIN_BASE}/outputs/visualizations/${scenario}_${dish}"
    done
done

# ── Helper ────────────────────────────────────────────────────────
ts() { date "+%H:%M:%S"; }
log() { echo "[$(ts)] [MASTER] $*" | tee -a "$MASTER_LOG"; }

# Initialize log
echo "" > "$MASTER_LOG"
echo "================================================================" | tee -a "$MASTER_LOG"
log "GLOMAP MASTER PIPELINE"
log "  Total dishes:   6"
log "  Parallelism:    2 dishes at a time"
log "  GPU:            RTX 3070 Ti"
log "  Matching:       Exhaustive (best quality)"
log "  Started:        $(date)"
echo "================================================================" | tee -a "$MASTER_LOG"

GLOBAL_START=$(date +%s)

# ── Run Function ──────────────────────────────────────────────────
run_dish() {
    local scenario=$1
    local dish=$2
    log ">>> STARTING ${scenario}/${dish}"
    bash "${SCRIPT_DIR}/run_glomap_dish.sh" "$scenario" "$dish" 0
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        log "<<< FINISHED ${scenario}/${dish} (SUCCESS)"
    else
        log "<<< FINISHED ${scenario}/${dish} (FAILED, exit code $exit_code)"
    fi
    return $exit_code
}

# ── Group 1 ───────────────────────────────────────────────────────
log ""
log "======== GROUP 1/3 ========"
run_dish "Dish_turning" "Dish_1" &
PID1=$!
run_dish "Me_walking" "Dish_1" &
PID2=$!

FAIL=0
wait $PID1 || FAIL=$((FAIL+1))
wait $PID2 || FAIL=$((FAIL+1))
log "Group 1 complete (failures: $FAIL)"

# ── Group 2 ───────────────────────────────────────────────────────
log ""
log "======== GROUP 2/3 ========"
run_dish "Dish_turning" "Dish_2" &
PID1=$!
run_dish "Me_walking" "Dish_2" &
PID2=$!

FAIL2=0
wait $PID1 || FAIL2=$((FAIL2+1))
wait $PID2 || FAIL2=$((FAIL2+1))
FAIL=$((FAIL+FAIL2))
log "Group 2 complete (failures: $FAIL2)"

# ── Group 3 ───────────────────────────────────────────────────────
log ""
log "======== GROUP 3/3 ========"
run_dish "Dish_turning" "Dish_3" &
PID1=$!
run_dish "Me_walking" "Dish_3" &
PID2=$!

FAIL3=0
wait $PID1 || FAIL3=$((FAIL3+1))
wait $PID2 || FAIL3=$((FAIL3+1))
FAIL=$((FAIL+FAIL3))
log "Group 3 complete (failures: $FAIL3)"

# ── Summary ───────────────────────────────────────────────────────
GLOBAL_END=$(date +%s)
GLOBAL_TIME=$((GLOBAL_END - GLOBAL_START))

echo "" | tee -a "$MASTER_LOG"
echo "================================================================" | tee -a "$MASTER_LOG"
log "ALL DISHES COMPLETE"
log "  Total Time: ${GLOBAL_TIME}s ($(( GLOBAL_TIME / 60 ))m $(( GLOBAL_TIME % 60 ))s)"
log "  Failures:   $FAIL / 6"
echo "================================================================" | tee -a "$MASTER_LOG"
echo "" | tee -a "$MASTER_LOG"

log "SUMMARY:"
echo "────────────────────────────────────────────────────────────" | tee -a "$MASTER_LOG"
printf "%-22s  %-6s  %-8s  %-8s  %-10s\n" "DISH" "STATUS" "REG" "POINTS" "REPROJ" | tee -a "$MASTER_LOG"
echo "────────────────────────────────────────────────────────────" | tee -a "$MASTER_LOG"

for scenario in "Dish_turning" "Me_walking"; do
    for dish in "Dish_1" "Dish_2" "Dish_3"; do
        METRICS="${WIN_BASE}/outputs/${scenario}/${dish}/metrics.json"
        LABEL="${scenario}/${dish}"
        if [ -f "$METRICS" ]; then
            STATUS=$(python3 -c "import json; print(json.load(open('$METRICS')).get('status','?'))" 2>/dev/null || echo "?")
            REG=$(python3 -c "import json; d=json.load(open('$METRICS')); print(f\"{d['registered_images']}/{d['total_images']}\")" 2>/dev/null || echo "?")
            PTS=$(python3 -c "import json; print(json.load(open('$METRICS'))['points_3d'])" 2>/dev/null || echo "?")
            ERR=$(python3 -c "import json; print(f\"{json.load(open('$METRICS'))['mean_reprojection_error_px']:.3f}px\")" 2>/dev/null || echo "?")
            printf "%-22s  %-6s  %-8s  %-8s  %-10s\n" "$LABEL" "$STATUS" "$REG" "$PTS" "$ERR" | tee -a "$MASTER_LOG"
        else
            printf "%-22s  %-6s  %-8s  %-8s  %-10s\n" "$LABEL" "FAIL" "-" "-" "-" | tee -a "$MASTER_LOG"
        fi
    done
done
echo "────────────────────────────────────────────────────────────" | tee -a "$MASTER_LOG"

echo "" | tee -a "$MASTER_LOG"
log "Next step: Run analyze_glomap.py on Windows to generate visualizations and report."
log "  python analyze_glomap.py"

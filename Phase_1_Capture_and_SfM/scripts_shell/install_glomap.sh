#!/bin/bash
# ================================================================
#  COLMAP + GLOMAP Installer for WSL2 Ubuntu 24.04
# ================================================================
#  This script installs COLMAP (with GPU/CUDA support) and GLOMAP
#  from source. Run once before using the GLOMAP pipeline.
#
#  Usage (run from WSL):
#    bash /mnt/d/glomap_pipeline/glomap_pipeline/install_glomap.sh
#
#  Requirements:
#    - WSL2 with Ubuntu 24.04
#    - NVIDIA GPU visible in WSL (nvidia-smi should work)
#    - ~5GB disk space
# ================================================================

set -euo pipefail

log() { echo -e "\n\033[1;36m[$(date +%H:%M:%S)] $*\033[0m"; }
err() { echo -e "\n\033[1;31m[ERROR] $*\033[0m"; exit 1; }

GLOMAP_DIR="$HOME/glomap_project"

# ── Check prerequisites ──────────────────────────────────────────
log "Checking prerequisites..."

if ! command -v nvidia-smi &>/dev/null; then
    err "nvidia-smi not found. Make sure NVIDIA drivers are installed on Windows and WSL2 GPU passthrough works."
fi

echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "  OS:  $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"

# ── Install system dependencies ──────────────────────────────────
log "Installing system dependencies (this may take a few minutes)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    cmake \
    ninja-build \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libqt5svg5-dev \
    libcgal-dev \
    libceres-dev \
    libgtest-dev \
    libopenimageio-dev \
    openimageio-tools \
    libopencv-dev \
    git

# ── Check CUDA toolkit ──────────────────────────────────────────
log "Checking CUDA..."
if command -v nvcc &>/dev/null; then
    echo "  CUDA: $(nvcc --version | grep release)"
else
    log "Installing CUDA toolkit..."
    # Install CUDA toolkit (headers + libraries for compilation)
    sudo apt-get install -y -qq nvidia-cuda-toolkit
    echo "  CUDA: $(nvcc --version 2>/dev/null | grep release || echo 'installed')"
fi

# ── Create project directory ─────────────────────────────────────
mkdir -p "$GLOMAP_DIR"
cd "$GLOMAP_DIR"

# ── Clone and build COLMAP ───────────────────────────────────────
log "Cloning COLMAP..."
if [ -d "colmap" ]; then
    echo "  COLMAP directory exists, pulling latest..."
    cd colmap && git pull --ff-only && cd ..
else
    git clone https://github.com/colmap/colmap.git
fi

log "Building COLMAP (with CUDA)..."
cd colmap
mkdir -p build && cd build

cmake .. -GNinja \
    -DCMAKE_CUDA_ARCHITECTURES="86" \
    -DCMAKE_BUILD_TYPE=Release

ninja -j4

log "Installing COLMAP..."
sudo ninja install

# Verify
if command -v colmap &>/dev/null; then
    echo "  COLMAP installed: $(colmap --version 2>&1 | head -1 || echo 'OK')"
else
    # If not on PATH, it's likely in /usr/local/bin
    export PATH="/usr/local/bin:$PATH"
    echo "  COLMAP at: $(which colmap 2>/dev/null || echo '/usr/local/bin/colmap')"
fi

cd "$GLOMAP_DIR"

# ── Clone and build GLOMAP ───────────────────────────────────────
log "Cloning GLOMAP..."
if [ -d "glomap" ]; then
    echo "  GLOMAP directory exists, pulling latest..."
    cd glomap && git pull --ff-only && cd ..
else
    git clone https://github.com/colmap/glomap.git
fi

log "Building GLOMAP..."
cd glomap
mkdir -p build && cd build

cmake .. -GNinja \
    -DCMAKE_BUILD_TYPE=Release

ninja -j4

cd "$GLOMAP_DIR"

# ── Verify installation ─────────────────────────────────────────
log "Verifying installation..."

COLMAP_PATH=$(which colmap 2>/dev/null || echo "NOT FOUND")
GLOMAP_PATH="$GLOMAP_DIR/glomap/build/glomap/glomap"

echo ""
echo "================================================================"
echo "  INSTALLATION COMPLETE"
echo "================================================================"
echo "  COLMAP:  $COLMAP_PATH"

if [ -f "$GLOMAP_PATH" ]; then
    echo "  GLOMAP:  $GLOMAP_PATH"
    echo ""
    echo "  [OK] Both tools are ready!"
else
    echo "  GLOMAP:  NOT FOUND at $GLOMAP_PATH"
    echo ""
    echo "  [!!] GLOMAP binary not found. Check the build output above."
fi

echo ""
echo "  You can now run the GLOMAP pipeline:"
echo "    bash /mnt/d/glomap_pipeline/glomap_pipeline/run_glomap_all.sh"
echo "================================================================"

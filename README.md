<div align="center">

<img src="assets/hero_banner.png" alt="WebAR Menu 3DGS Banner" width="100%" />

# 🍔 WebAR Menu Pipeline (3D Gaussian Splatting)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-CUDA%20Accelerated-ee4c2c?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![GLOMAP](https://img.shields.io/badge/GLOMAP-SfM-000000?style=for-the-badge&logo=github)](https://github.com/colmap/glomap)
[![WebAR](https://img.shields.io/badge/WebAR-SuperSplat-FF004E?style=for-the-badge)](https://playcanvas.com/supersplat/editor)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=for-the-badge)]()

*A highly optimized, end-to-end 3D Gaussian Splatting pipeline designed specifically for capturing hyper-realistic food dishes and compressing them for WebAR mobile browsers—built for consumer hardware (8GB VRAM).*

</div>

---

## 📖 Overview

The **WebAR Menu Pipeline** is an academic research project and full production codebase that translates raw video of food dishes into interactive, 60-FPS WebAR experiences. Standard 3DGS produces massive ~1.5 GB `.ply` files that crush mobile browsers. This pipeline implements custom **Spherical Harmonics Reduction**, **Spatial Bounding Boxes**, and **Alpha Masking** to compress photorealistic models below **80 MB**, allowing seamless integration into digital restaurant menus.

---

## 🏗️ Architecture & Phases

The repository is modularly structured into three distinct phases of the production pipeline.

### Phase 1: Capture & Structure-from-Motion (SfM)
> 📁 **`Phase_1_Capture_and_SfM`**

The preprocessing phase translates raw video captures into mathematically structured data.
- **Automated Frame Extraction:** Extracts crystal-clear, unblurred frames from turntable captures.
- **Background Deletion:** Implements `rembg` (U2Net) to create 2D Alpha Masks, allowing the rasterizer to natively ignore background noise.
- **GLOMAP Engine:** Uses Global Structure-from-Motion (SfM) to solve camera extrinsics drastically faster than traditional COLMAP.

### Phase 2: 3DGS Training Engine
> 📁 **`Phase_2_3DGS_Training`**

The core PyTorch engine, heavily modified from the original Inria implementation to prevent hardware bottlenecks.
- **3D Spatial Bounding Boxes:** A custom PyTorch injection (`train_glomap.py`) that calculates Euclidean distances during densification to instantly delete point clouds that drift outside the target radius.
- **VRAM Optimization:** Bypasses "Hedgehog Overfitting" anomalies to keep training well within the 8 GB limit of consumer GPUs.
- **WebAR Compressor:** The `optimize_webar.py` script automatically strips non-essential Spherical Harmonics (preserving Degree 2 for glossy reflections), slicing payload sizes by up to 50% without visual degradation.

### Phase 3: WebAR Client
> 📁 **`Phase_3_WebAR_Client`**

The frontend deployment phase. This folder is reserved for the integration team to deploy PlayCanvas/SuperSplat `.html` templates that parse the optimized `.ply` files onto mobile browsers.

---

## 🧬 Pipeline Workflow

The entire logic flows sequentially as mapped out below:

```mermaid
graph TD
    A[Raw Video Capture] -->|Turntable / Dish_turning| B(Frame Extraction)
    B --> C(2D Alpha Masking)
    C --> D[GLOMAP SfM]
    
    D -->|Sparse Point Cloud| E(3DGS PyTorch Engine)
    
    E --> F{VRAM Optimization}
    F -->|Densify Grad = 0.0001| G[High-Fidelity 3D Model]
    
    G --> H(WebAR Optimizer)
    H -->|SH Degree 2 Cap| I((Sub-80MB .ply Payload))
    
    I --> J[SuperSplat Web Client]
    J --> K[Mobile AR Restaurant Menu]
    
    style E fill:#ee4c2c,stroke:#333,stroke-width:2px,color:#fff
    style I fill:#00d26a,stroke:#333,stroke-width:2px,color:#fff
    style J fill:#FF004E,stroke:#333,stroke-width:2px,color:#fff
```

---

## 🔬 Academic Documentation

This codebase is accompanied by rigorous academic documentation detailing the mathematical constraints and physical experiments performed.

> 📚 **Read the full Thesis Document:** [`Docs/project_doc.md`](Docs/project_doc.md)

**Key Discoveries Documented:**
*   **The Bounding Box Paradox:** Mathematical proof of why `Me_walking` (dynamic camera) capture strategies fail under 3D bounding box isolation due to PyTorch L1 Loss function panic.
*   **The Hedgehog Anomaly:** Documentation on how aggressive Densification Gradients destroy geometry on consumer hardware.
*   **Turntable Superiority:** Physical validation of the `Dish_turning` method as an organic, natural spatial isolator.

---

## 🚀 Quick Start

To run the production training pipeline on a newly preprocessed dish:

```bash
# 1. Activate the Conda Environment
conda activate gaussian_splatting

# 2. Navigate to Phase 2
cd Phase_2_3DGS_Training

# 3. Execute the Automated WebAR Pipeline
.\train_glomap_v2.bat
```

*The script will automatically train the model for 30,000 iterations, run the WebAR compression logic, and output a `point_cloud_web.ply` ready for web deployment.*

---

<div align="center">
<i>Built for the future of interactive dining.</i>
</div>

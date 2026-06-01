# WebAR Menu Pipeline (3DGS)

This repository contains the complete end-to-end pipeline for capturing, processing, and rendering hyper-realistic 3D food models for WebAR deployment using 3D Gaussian Splatting (3DGS).

## Architecture

This pipeline was specifically optimized for consumer-grade hardware (RTX 3070 Ti, 8GB VRAM) and strict mobile browser WebAR constraints (<80 MB `.ply` payloads). 

### Phase 1: Capture & SfM (`/Phase_1_Capture_and_SfM`)
Contains the automated preprocessing scripts:
- Video-to-frames extraction
- Automated background removal (2D Alpha Masking via `rembg`)
- Sparse point cloud triangulation using GLOMAP

### Phase 2: 3DGS Training (`/Phase_2_3DGS_Training`)
Contains the custom PyTorch engine and production batch scripts:
- **Spatial Isolation:** Custom `--bounding_box` logic injected into `train_glomap.py` to dynamically delete background geometry during densification.
- **WebAR Optimization:** `optimize_webar.py` automatically converts raw training models into web-ready formats by discarding high-degree Spherical Harmonics (preserving Degree 2 for glossy reflections).

### Phase 3: WebAR Client (`/Phase_3_WebAR_Client`)
Contains the frontend WebGL/SuperSplat integration code for loading the highly compressed `.ply` models into the client-facing AR viewer.

## Documentation
Please refer to `Docs/project_doc.md` for the complete academic thesis detailing the algorithmic choices, hardware profiling, and mathematical paradoxes (such as the "Me_walking" L1 Loss panic) resolved during development.

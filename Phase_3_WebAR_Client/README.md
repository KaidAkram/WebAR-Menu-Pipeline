# Gourmet AR Menu — v2

Ultra-realistic, interactive 3D food preview built on WebXR, Three.js, and Gaussian Splats 3D. Every dish renders at its true 1:1 physical scale in augmented reality.

---

## ✨ What's New in v2

### Performance
| Feature | Implementation |
|---|---|
| **Web Worker depth sort** | `splat-worker.js` — sort runs entirely off the main thread; Wasm scaffold ready for drop-in |
| **Dynamic Resolution Scaling (DRS)** | Worker monitors FPS every 60 frames; if < 30 fps the worker posts a `drsChanged` signal and the main thread lowers `renderer.setPixelRatio()` (full → 1.0 → 0.75). Recovers automatically above 50 fps |
| **Frustum culling** | Three.js `Frustum` class updated every frame; culled objects never reach the GPU. Worker also exposes `FRUSTUM_CULL` for off-thread AABB pre-passes |
| **Progressive streaming** | Worker's `STREAM_KSPLAT` fetches in 512 KB chunks and reports progress; loading overlay shows live `%`. GaussianSplats3D's own progressive loader handles actual WebGL upload |

### AR Positioning
| Feature | Implementation |
|---|---|
| **Horizontal surface filter** | Hit-test matrix Y-column (surface normal) must be > 0.85 (≈ ±32°). Walls and chairs rejected with a user hint |
| **Locked 1:1 scale** | `dishData.realSize` (metres) in `dishes.json` → `scaleFactor = realSize / maxDim`. Scale is re-locked every frame in AR mode; user cannot pinch-scale |
| **Smooth reticle** | `THREE.Vector3.lerp()` at factor 0.18 per frame; reticle glides across surfaces |
| **Single-axis Y rotation** | After placement, one-finger horizontal drag rotates the dish only on the Y axis. All other movement locked |

### Visual Fidelity
| Feature | Implementation |
|---|---|
| **WebXR Lighting Estimation** | `session.requestLightProbe()` → reads `primaryLightIntensity` RGB and direction each frame → applied to `dirLight` colour + intensity |
| **Proxy-mesh shadows** | Invisible `CylinderGeometry` proxy casts real dynamic shadows; `ShadowMaterial` plane receives them |
| **Blob shadow fallback** | `MeshBasicMaterial` plane with a baked texture; activated automatically when DRS reaches level 2 (< 30 fps) |
| **Premium reticle** | Outer ring + inner dot + 4 radial ticks; pulsing scale animation while scanning |

### Interactive "Diegetic" UI
| Feature | Implementation |
|---|---|
| **Proxy-mesh raycasting** | `Raycaster.intersectObject(interactionMesh)` — clicks on the invisible cylinder, not the raw point cloud |
| **Spatial 3D info card** | `three-mesh-ui` loaded dynamically; card is a physical Three.js `Block` object in the scene |
| **LookAt camera** | `spatialCard.lookAt(camera.position)` called every frame so the card always faces the viewer |
| **Pop-in animation** | Card scales from 0.01 → 1 via lerp on reveal; reverses on dismiss |
| **HTML overlay fallback** | If `three-mesh-ui` fails to import, the existing glassmorphic HTML panel is used instead |

---

## 📁 Project Structure

```
├── index.html          Main entry (importmap pinned, three-mesh-ui global hook)
├── styles.css          All styles + pipeline badges + DRS indicator
├── main.js             Core: routing, Three.js, WebXR, DRS, lighting, spatial UI
├── splat-worker.js     Web Worker: depth sort, frustum cull, stream, DRS signals
└── assets/
    ├── dishes.json     Menu database (see schema below)
    ├── pizza_colmap.ksplat     Test 1 — Pizza / Colmap pipeline
    ├── burger_glomap.ksplat    Test 2 — Burger / Glomap pipeline
    ├── pizza_glomap.ksplat     Test 3 — Pizza / Glomap pipeline
    ├── sandwich_glomap.ksplat  Test 4 — Poutine Sandwich / Glomap pipeline
    ├── images/
    │   ├── pizza.jpg
    │   ├── burger.jpg
    │   ├── pizza_truffle.jpg
    │   └── sandwich.jpg
    └── shadows/        (optional baked blob shadows)
        ├── pizza_shadow.png
        ├── burger_shadow.png
        └── sandwich_shadow.png
```

---

## `dishes.json` Schema

```json
{
  "id":          "unique-slug",
  "name":        "Display Name",
  "price":       "$00.00",
  "calories":    "000 kcal",
  "description": "...",
  "file":        "model.ksplat",
  "pipeline":    "Colmap | Glomap",   // shown as badge on card
  "realSize":    0.25,                 // diameter/height in METRES (for 1:1 AR scale)
  "image":       "assets/images/photo.jpg",
  "blobShadow":  "assets/shadows/shadow.png"  // optional fallback shadow
}
```

---

## 🚀 Getting Started

Must be served over HTTP (ES modules + `fetch` require it):

```bash
# Python
python -m http.server 8000

# Node
npx serve .
# or
npx http-server -p 8000
```

WebXR AR requires HTTPS on a physical device (localhost is exempt).

---

## 🔬 Test Asset Notes

| File | Pipeline | Key observation |
|---|---|---|
| `pizza_colmap.ksplat` | Colmap (SfM) | Baseline point-cloud density; useful for comparing splat distribution vs Glomap |
| `burger_glomap.ksplat` | Glomap | Global pose estimation — note alignment accuracy in flat AR placement |
| `pizza_glomap.ksplat` | Glomap | Compare with Colmap pizza: load time, splat density, rendering alignment |
| `sandwich_glomap.ksplat` | Glomap | Tall, multi-layer subject — tests Y-axis scale accuracy and vertical alignment |

Glomap's global camera pose estimation generally produces tighter point-cloud alignment, which should reduce rendering drift in WebAR. Compare `hitTestSource` placement accuracy between the Colmap and Glomap pizza files in the same environment.

---

## 🛠 Wasm Integration

`splat-worker.js` contains a scaffold for a compiled `splat-sort.wasm`:

1. Compile your sort algorithm to Wasm (e.g. with Emscripten or Rust/wasm-pack).
2. Place `splat-sort.wasm` alongside `splat-worker.js`.
3. In `initWasm()`, replace the placeholder with:
   ```js
   const res = await fetch(new URL('splat-sort.wasm', self.location.href));
   const { instance } = await WebAssembly.instantiateStreaming(res, importObj);
   wasmExports = instance.exports;
   wasmReady   = true;
   ```
4. In `sortSplatsByDepth()`, the `wasmReady` branch calls `wasmExports.sortSplats()`.

---

## 📜 License

MIT

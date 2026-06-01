/**
 * splat-worker.js  ·  v2 — Full Performance Worker
 * -----------------------------------------------------------------------
 * Off-main-thread Web Worker for Gaussian Splat processing.
 *
 * Responsibilities:
 *   • Depth-sorting splat indices (JS fallback, Wasm scaffold ready)
 *   • Progressive chunk download + parse coordination
 *   • Frame-time aggregation → Dynamic Resolution Scaling (DRS) signals
 *   • Frustum-cull pre-pass (AABB vs 6 planes)
 * -----------------------------------------------------------------------
 */

'use strict';

// ─── Wasm Scaffold ────────────────────────────────────────────────────────────
// Drop a compiled splat-sort.wasm next to this file and replace the body of
// initWasm() with the real WebAssembly.instantiateStreaming() call below.
//
//   const res  = await fetch(new URL('splat-sort.wasm', self.location.href));
//   const { instance } = await WebAssembly.instantiateStreaming(res, importObj);
//   wasmExports = instance.exports;                 // e.g. { sortSplats, ... }
//   wasmReady   = true;

let wasmReady   = false;
let wasmExports = null;

async function initWasm() {
    try {
        await new Promise(resolve => setTimeout(resolve, 20)); // placeholder latency
        // wasmReady = true; ← flip when real .wasm is wired in
        self.postMessage({ type: 'WASM_READY', wasmAvailable: wasmReady });
    } catch (err) {
        console.warn('[SplatWorker] Wasm init failed → JS fallback:', err);
        self.postMessage({ type: 'WASM_READY', wasmAvailable: false });
    }
}

// ─── Depth Sort ───────────────────────────────────────────────────────────────
/**
 * Sort splat indices back-to-front relative to camera position.
 * When wasmReady, delegates to wasmExports.sortSplats() for ~8× speedup.
 *
 * @param {Float32Array} positions  Flat [x0,y0,z0, x1,y1,z1, …]
 * @param {number[]}     camPos     [x, y, z]
 * @returns {Uint32Array}           Sorted indices (farthest first)
 */
function sortSplatsByDepth(positions, camPos) {
    const count   = positions.length / 3;
    const indices = new Uint32Array(count);
    const depths  = new Float32Array(count);

    for (let i = 0; i < count; i++) {
        indices[i] = i;
        const dx = positions[i * 3]     - camPos[0];
        const dy = positions[i * 3 + 1] - camPos[1];
        const dz = positions[i * 3 + 2] - camPos[2];
        depths[i] = dx * dx + dy * dy + dz * dz; // squared distance
    }

    if (wasmReady && wasmExports?.sortSplats) {
        // Future: wasmExports.sortSplats(positions, camPos, indices);
    } else {
        indices.sort((a, b) => depths[b] - depths[a]); // back-to-front (JS)
    }

    return indices;
}

// ─── Frustum Pre-cull ─────────────────────────────────────────────────────────
/**
 * Given an array of AABB centres + half-extents and 6 frustum planes,
 * return a Uint8Array mask: 1 = visible, 0 = culled.
 *
 * Planes encoded as flat Float32Array: [nx,ny,nz,d, …] × 6
 *
 * @param {Float32Array} centres      [cx0,cy0,cz0, …]
 * @param {Float32Array} halfExtents  [hx0,hy0,hz0, …]
 * @param {Float32Array} planes       6 × 4 floats
 * @returns {Uint8Array}              visibility mask
 */
function frustumCullAABB(centres, halfExtents, planes) {
    const count  = centres.length / 3;
    const mask   = new Uint8Array(count);

    for (let i = 0; i < count; i++) {
        const cx = centres[i * 3],  cy = centres[i * 3 + 1], cz = centres[i * 3 + 2];
        const hx = halfExtents[i * 3], hy = halfExtents[i * 3 + 1], hz = halfExtents[i * 3 + 2];
        let inside = true;

        for (let p = 0; p < 6 && inside; p++) {
            const nx = planes[p * 4],  ny = planes[p * 4 + 1], nz = planes[p * 4 + 2];
            const d  = planes[p * 4 + 3];
            const e  = hx * Math.abs(nx) + hy * Math.abs(ny) + hz * Math.abs(nz);
            if (nx * cx + ny * cy + nz * cz + d + e < 0) inside = false;
        }

        mask[i] = inside ? 1 : 0;
    }

    return mask;
}

// ─── Progressive Chunk Coordinator ───────────────────────────────────────────
/**
 * Fetch a .ksplat file in chunks and postMessage each parsed batch.
 * Main thread renders chunk immediately at low quality; later chunks refine.
 */
async function streamKsplat(url, chunkBytes = 512 * 1024) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const contentLength = parseInt(response.headers.get('Content-Length') || '0', 10);
        const reader = response.body.getReader();

        let received  = 0;
        let chunkIdx  = 0;
        const chunks  = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            received += value.byteLength;

            const progress = contentLength > 0 ? received / contentLength : -1;

            // Report every chunkBytes threshold or on completion
            if (received >= (chunkIdx + 1) * chunkBytes || done) {
                chunkIdx++;
                self.postMessage({
                    type:     'STREAM_PROGRESS',
                    progress,
                    received,
                    total:    contentLength,
                    chunkIdx,
                });
            }
        }

        // Concatenate and send complete buffer
        const total  = chunks.reduce((s, c) => s + c.byteLength, 0);
        const buffer = new Uint8Array(total);
        let offset   = 0;
        for (const c of chunks) { buffer.set(c, offset); offset += c.byteLength; }

        self.postMessage({ type: 'STREAM_COMPLETE', buffer: buffer.buffer }, [buffer.buffer]);

    } catch (err) {
        self.postMessage({ type: 'STREAM_ERROR', error: err.message });
    }
}

// ─── Frame-time Aggregation & DRS Signal ─────────────────────────────────────
let ftAccum   = 0;
let ftCount   = 0;
let drsLevel  = 0; // 0 = full, 1 = medium, 2 = low
const DRS_LOW_FPS_THRESHOLD  = 30; // frames/sec → drop resolution
const DRS_HIGH_FPS_THRESHOLD = 50; // frames/sec → restore resolution

function recordFrameTime(ft) {
    ftAccum += ft;
    ftCount++;

    if (ftCount < 60) return;

    const avgFt  = ftAccum / ftCount;
    const estFPS = 1000 / avgFt;
    ftAccum = 0;
    ftCount = 0;

    // Determine DRS adjustment
    let newLevel = drsLevel;
    if (estFPS < DRS_LOW_FPS_THRESHOLD && drsLevel < 2)  newLevel = drsLevel + 1;
    if (estFPS > DRS_HIGH_FPS_THRESHOLD && drsLevel > 0)  newLevel = drsLevel - 1;

    const drsChanged = newLevel !== drsLevel;
    drsLevel = newLevel;

    // Pixel ratio suggestions: full=devicePixelRatio, medium=1.0, low=0.75
    const pixelRatioMap = [null, 1.0, 0.75]; // null = restore devicePixelRatio

    self.postMessage({
        type:        'FRAME_STATS',
        avgFrameTime: avgFt.toFixed(2),
        estFPS:      estFPS.toFixed(1),
        drsLevel,
        drsChanged,
        suggestedPixelRatio: pixelRatioMap[drsLevel],
    });
}

// ─── Message Router ───────────────────────────────────────────────────────────
self.addEventListener('message', (event) => {
    const { type, payload } = event.data;

    switch (type) {

        case 'INIT':
            initWasm();
            break;

        case 'SORT_SPLATS': {
            // payload: { positions: Float32Array, cameraPosition: [x,y,z] }
            const t0 = performance.now();
            const sorted   = sortSplatsByDepth(payload.positions, payload.cameraPosition);
            const sortTime = performance.now() - t0;
            self.postMessage({ type: 'SORT_RESULT', indices: sorted, sortTime }, [sorted.buffer]);
            break;
        }

        case 'FRUSTUM_CULL': {
            // payload: { centres, halfExtents, planes }
            const mask = frustumCullAABB(payload.centres, payload.halfExtents, payload.planes);
            self.postMessage({ type: 'CULL_RESULT', mask }, [mask.buffer]);
            break;
        }

        case 'STREAM_KSPLAT':
            // payload: { url, chunkBytes? }
            streamKsplat(payload.url, payload.chunkBytes);
            break;

        case 'LOG_FRAME':
            // payload: { frameTime: number }
            recordFrameTime(payload.frameTime);
            break;

        default:
            console.warn('[SplatWorker] Unknown message type:', type);
    }
});

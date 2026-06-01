import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ARButton } from 'three/addons/webxr/ARButton.js';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

export function createWebGLApp(container, dishData, callbacks) {
  let isDestroyed = false;
  const onProgress = callbacks.onProgress || (() => { });
  const onLoad = callbacks.onLoad || (() => { });
  const onError = callbacks.onError || (() => { });
  const onTap = callbacks.onTap || (() => { });
  const onARStart = callbacks.onARStart || (() => { });
  const onAREnd = callbacks.onAREnd || (() => { });
  const onARPlaced = callbacks.onARPlaced || (() => { });

  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  const BASE_PIXEL_RATIO = Math.min(window.devicePixelRatio, isMobile ? 1.5 : 2.5);

  let splatWorker = null;
  let drsLevel = 0;
  if (typeof Worker !== 'undefined') {
    splatWorker = new Worker('/public/splat-worker.js');
    splatWorker.postMessage({ type: 'INIT' });
    splatWorker.addEventListener('message', e => {
      if (isDestroyed) return;
      const { type } = e.data;
      if (type === 'FRAME_STATS') {
        const { drsChanged, suggestedPixelRatio, drsLevel: lvl } = e.data;
        drsLevel = lvl;
        if (drsChanged) {
          const pr = suggestedPixelRatio ?? BASE_PIXEL_RATIO;
          renderer.setPixelRatio(pr);
        }
      }
      if (type === 'STREAM_PROGRESS') {
        const pct = e.data.progress >= 0
          ? Math.round(e.data.progress * 100) + '%'
          : `${Math.round(e.data.received / 1024)}KB`;
        onProgress(pct);
      }
    });
  }

  // ── Scene Setup ───────────────────────────────────────────────────────────
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);

  const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.01, 100);
  camera.position.set(0, 0.5, 2.0);  // neutral; overridden after model loads

  const renderer = new THREE.WebGLRenderer({ antialias: !isMobile, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(BASE_PIXEL_RATIO);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.xr.enabled = true;
  container.appendChild(renderer.domElement);

  // ── Orbit Controls ────────────────────────────────────────────────────────
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.7;
  controls.enableZoom = true;
  controls.enablePan = false;
  controls.minDistance = 0.05;
  controls.maxDistance = 5;
  // Target the centre of where the dish will sit
  controls.target.set(0, 0, 0);
  controls.touches = {
    ONE: THREE.TOUCH.ROTATE,
    TWO: THREE.TOUCH.DOLLY_ROTATE
  };

  // ── Lights ────────────────────────────────────────────────────────────────
  const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 1.5);
  hemiLight.position.set(0, 2, 0);
  scene.add(hemiLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
  dirLight.position.set(1.5, 3, 2);
  scene.add(dirLight);

  // ── WebXR Lighting Estimation ─────────────────────────────────────────────
  let xrLightProbe = null;
  let xrDirectionalLight = null;

  function setupLightingEstimation(session) {
    if (!('requestLightProbe' in session)) return;
    session.requestLightProbe()
      .then(probe => {
        xrLightProbe = probe;
        xrDirectionalLight = new THREE.DirectionalLight();
        xrDirectionalLight.intensity = 0;
        scene.add(xrDirectionalLight);
        probe.addEventListener('reflectionchange', () => {
          if (renderer.xr.getEnvironmentBlendMode() === 'additive') return;
          scene.environment = renderer.xr.getLightProbeTarget(probe);
        });
      })
      .catch(err => console.warn('[Lighting]', err));
  }

  function updateLightingEstimation(frame) {
    if (!xrLightProbe || !frame.getLightEstimate) return;
    const est = frame.getLightEstimate(xrLightProbe);
    if (!est) return;
    const intensity = Math.max(est.primaryLightIntensity.x, est.primaryLightIntensity.y, est.primaryLightIntensity.z);
    dirLight.intensity = Math.min(intensity * 0.5, 3.0);
    dirLight.color.setRGB(
      Math.min(est.primaryLightIntensity.x / (intensity || 1), 1),
      Math.min(est.primaryLightIntensity.y / (intensity || 1), 1),
      Math.min(est.primaryLightIntensity.z / (intensity || 1), 1)
    );
    if (xrDirectionalLight && est.primaryLightDirection) {
      xrDirectionalLight.position.copy(est.primaryLightDirection).negate();
      xrDirectionalLight.intensity = intensity * 0.3;
    }
  }

  // ── AR Button ─────────────────────────────────────────────────────────────
  const overlayNode = container.parentElement;
  const arButton = ARButton.createButton(renderer, {
    requiredFeatures: ['hit-test'],
    optionalFeatures: ['light-estimation', 'dom-overlay'],
    domOverlay: { root: overlayNode },
  });
  arButton.style.bottom = '30px';
  arButton.style.padding = '12px 24px';
  arButton.style.borderRadius = '30px';
  arButton.style.background = 'rgba(255,255,255,0.1)';
  arButton.style.backdropFilter = 'blur(10px)';
  arButton.style.border = '1px solid rgba(255,255,255,0.2)';
  arButton.style.color = '#fff';
  arButton.style.fontWeight = '500';
  arButton.style.fontFamily = 'Outfit, sans-serif';
  container.parentElement.appendChild(arButton);

  renderer.xr.addEventListener('sessionstart', () => {
    onARStart();
    scene.background = null;
    // Hide the dish until the reticle finds a surface
    arAnchorGroup.visible = false;
    setupLightingEstimation(renderer.xr.getSession());
  });

  renderer.xr.addEventListener('sessionend', () => {
    onAREnd();
    scene.background = new THREE.Color(0x1a1a2e);
    isPlaced = false;
    placedRotationY = 0;
    arAnchorGroup.rotation.set(0, 0, 0);
    // Restore preview position/scale
    arAnchorGroup.position.set(0, 0, 0);
    arAnchorGroup.visible = true;
    arAnchorGroup.scale.setScalar(scaleFactor);
  });

  // ── Reticle (can be toggled on/off) ───────────────────────────────────────
  const reticleGroup = new THREE.Group();
  const outerRing = new THREE.Mesh(
    new THREE.RingGeometry(0.12, 0.14, 40).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 })
  );
  const innerDot = new THREE.Mesh(
    new THREE.RingGeometry(0.01, 0.03, 24).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0xffffff })
  );
  reticleGroup.add(outerRing, innerDot);
  reticleGroup.matrixAutoUpdate = false;
  reticleGroup.visible = false;
  scene.add(reticleGroup);
  let showReticleVisual = false;

  // ── AR anchor group ───────────────────────────────────────────────────────
  const arAnchorGroup = new THREE.Group();
  arAnchorGroup.visible = true;
  arAnchorGroup.position.set(0, 0, 0);
  scene.add(arAnchorGroup);

  let isPlaced = false;
  let placedRotationY = 0;
  let hitTestSource = null;
  let hitTestSourceRequested = false;

  const _tmpPos = new THREE.Vector3();
  const _tmpQuat = new THREE.Quaternion();
  const _tmpScl = new THREE.Vector3();

  // ── Model state ───────────────────────────────────────────────────────────
  let interactionMesh = null;
  let shadowPlane = null;
  let blobShadowMesh = null;
  let modelLoaded = false;
  let scaleFactor = 0.05;
  let splatViewer = null;

  function startProgressiveStream(url) {
    if (splatWorker) {
      splatWorker.postMessage({ type: 'STREAM_KSPLAT', payload: { url, chunkBytes: 512 * 1024 } });
    }
  }

  async function loadModel(filePath) {
    const ext = filePath.split('.').pop().toLowerCase();
    if (ext === 'ksplat' || ext === 'splat') {
      startProgressiveStream(`/assets/${dishData.file}`);

      splatViewer = new GaussianSplats3D.DropInViewer({
        dynamicScene: true,
        sharedMemoryForWorkers: false,
        gpuAcceleratedSort: false,
        ignoreDevicePixelRatio: true,
        selfDrivenMode: false
      });

      arAnchorGroup.add(splatViewer);

      if (dishData.pipeline === 'Glomap') scaleFactor = 0.15;
      else if (dishData.pipeline === 'Colmap') scaleFactor = 0.30;
      else scaleFactor = 0.20;

      await splatViewer.addSplatScene(`/assets/${dishData.file}`, {
        splatAlphaRemovalThreshold: isMobile ? 10 : 1,
        showLoadingUI: false,
        position: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
      });

      splatViewer.frustumCulled = false;
      splatViewer.visible = true;
      // Splat stays at local y=0; the plate is offset below it in post-load.
      return splatViewer;
    }
    throw new Error('Only .ksplat/.splat supported.');
  }
  // ── Post-load setup ────────────────────────────────────────────────
  const splatPath = `/assets/${dishData.file}`;
  console.log('Loading splat:', splatPath);

  // Verify the file actually exists before handing it to the Viewer (avoids
  // an infinite loading screen on 404).
  fetch(splatPath, { method: 'HEAD' })
    .then(res => {
      if (!res.ok) throw new Error(`Asset not found: ${splatPath} (HTTP ${res.status})`);
      return loadModel(splatPath);
    })
    .then(() => {
      if (isDestroyed) return;

      // Poll until the splat geometry is ready (GPU upload lags behind promise resolve)
      function waitAndAlign(attemptsLeft) {
        if (isDestroyed) return;
        //test
        // Measure in unscaled local space to avoid world↔local errors
        arAnchorGroup.scale.setScalar(1);
        arAnchorGroup.updateMatrixWorld(true);
        const box = new THREE.Box3().setFromObject(splatViewer);
        const size = new THREE.Vector3();
        box.getSize(size);

        if (size.length() < 0.0001) {
          // Geometry not ready yet — restore a sane scale and retry
          arAnchorGroup.scale.setScalar(scaleFactor);
          if (attemptsLeft > 0) {
            requestAnimationFrame(() => waitAndAlign(attemptsLeft - 1));
          }
          return;
        }

        const centre = new THREE.Vector3();
        box.getCenter(centre);

        // 1. Centre XZ on anchor; place dish bottom exactly at Y=0
        splatViewer.position.x = -centre.x;
        splatViewer.position.z = -centre.z;
        splatViewer.position.y = -box.min.y;

        // 2. Scale so the dish fills its real-world size (realSize is in metres)
        const maxDimension = Math.max(size.x, size.z); // use footprint, not height
        const realSize = dishData.realSize ?? 0.25;
        scaleFactor = maxDimension > 0 ? realSize / maxDimension : 0.05;

        arAnchorGroup.scale.setScalar(scaleFactor);
        arAnchorGroup.updateMatrixWorld(true);

        // 3. Frame the camera for the 3D preview (not AR — AR uses hit-test pose)
        const worldSpan = Math.max(size.x, size.y, size.z) * scaleFactor;
        const worldMidY = (size.y * 0.5) * scaleFactor;
        controls.target.set(0, worldMidY, 0);
        camera.position.set(0, worldMidY + worldSpan * 0.4, worldSpan * 1.2);
        controls.update();

        // 4. Invisible interaction cylinder for tap detection
        const proxyR = Math.max(size.x, size.z) * 0.5;
        const proxyH = size.y;
        interactionMesh = new THREE.Mesh(
          new THREE.CylinderGeometry(proxyR, proxyR, proxyH, 24),
          new THREE.MeshStandardMaterial({ visible: false, side: THREE.DoubleSide })
        );
        interactionMesh.position.y = proxyH * 0.5; // centred vertically above ground
        arAnchorGroup.add(interactionMesh);

        // 5. Apply calibration overrides from dishes.json (if present)
        if (dishData.arScale != null) {
          arAnchorGroup.scale.setScalar(dishData.arScale);
        }
        if (dishData.offsetX != null || dishData.offsetY != null || dishData.offsetZ != null) {
          arAnchorGroup.position.set(
            dishData.offsetX ?? 0,
            dishData.offsetY ?? 0,
            dishData.offsetZ ?? 0
          );
        }

        modelLoaded = true;
        onLoad();
      }

      // Start polling — up to 90 frames (~1.5 s at 60 fps)
      requestAnimationFrame(() => waitAndAlign(90));

    })
    .catch(err => {
      console.error('[WebGLApp] Load failed:', err);
      if (!isDestroyed) onError(err);
    });

  // ── Raycasting ────────────────────────────────────────────────────────────
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  function onPointerDown(event) {
    if (!interactionMesh || !modelLoaded || renderer.xr.isPresenting) return;
    if (event.target !== renderer.domElement) return;
    const cx = event.changedTouches ? event.changedTouches[0].clientX : event.clientX;
    const cy = event.changedTouches ? event.changedTouches[0].clientY : event.clientY;
    pointer.x = (cx / window.innerWidth) * 2 - 1;
    pointer.y = (cy / window.innerHeight) * -2 + 1;
    raycaster.setFromCamera(pointer, camera);
    if (raycaster.intersectObject(interactionMesh).length > 0) onTap();
  }

  renderer.domElement.addEventListener('pointerdown', onPointerDown);

  // ── Y-rotation after placement ────────────────────────────────────────────
  let isRotating = false;
  let rotateStartX = 0;
  let rotateStartY = 0;

  renderer.domElement.addEventListener('touchstart', e => {
    if (isPlaced && e.touches.length === 1) {
      isRotating = true;
      rotateStartX = e.touches[0].clientX;
      rotateStartY = placedRotationY;
    }
  }, { passive: true });

  renderer.domElement.addEventListener('touchmove', e => {
    if (isPlaced && isRotating && e.touches.length === 1) {
      placedRotationY = rotateStartY + (e.touches[0].clientX - rotateStartX) * 0.01;
      arAnchorGroup.rotation.y = placedRotationY;
    }
  }, { passive: true });

  renderer.domElement.addEventListener('touchend', () => { isRotating = false; });

  // ── XR Controller ─────────────────────────────────────────────────────────
  const controller = renderer.xr.getController(0);
  const tempMatrix = new THREE.Matrix4();
  const xrRaycaster = new THREE.Raycaster();

  let hasValidHit = false;

  controller.addEventListener('select', () => {
    if (!modelLoaded) return;
    if (!isPlaced && hasValidHit) {
      isPlaced = true;
      hasValidHit = false;
      onARPlaced();
    } else if (isPlaced && interactionMesh) {
      tempMatrix.identity().extractRotation(controller.matrixWorld);
      xrRaycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
      xrRaycaster.ray.direction.set(0, 0, -1).applyMatrix4(tempMatrix);
      if (xrRaycaster.intersectObject(interactionMesh).length > 0) onTap();
    }
  });

  scene.add(controller);

  const onWindowResize = () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  };
  window.addEventListener('resize', onWindowResize);

  let _fpsPrev = performance.now();
  let _fpsFrames = 0;

  // ── RENDER LOOP ───────────────────────────────────────────────────────────
  renderer.setAnimationLoop((timestamp, frame) => {
    if (isDestroyed) return;

    _fpsFrames++;
    const _now = performance.now();
    const _elapsed = _now - _fpsPrev;
    if (_elapsed >= 500) {
      if (splatWorker) splatWorker.postMessage({ type: 'LOG_FRAME', payload: { frameTime: _elapsed / _fpsFrames } });
      if (blobShadowMesh) {
        blobShadowMesh.visible = (drsLevel >= 2);
        if (shadowPlane) shadowPlane.visible = (drsLevel < 2);
      }
      _fpsFrames = 0;
      _fpsPrev = _now;
    }

    controls.update();

    // Animate reticle ring pulse
    if (reticleGroup.visible && showReticleVisual) {
      outerRing.scale.setScalar(1 + Math.sin(timestamp / 200) * 0.05);
      outerRing.material.opacity = 0.7 + Math.sin(timestamp / 200) * 0.3;
    }    // ── AR hit-test ───────────────────────────────────────────────────────
    if (renderer.xr.isPresenting && frame) {
      const refSpace = renderer.xr.getReferenceSpace();
      const session = renderer.xr.getSession();

      updateLightingEstimation(frame);

      if (!hitTestSourceRequested) {
        session.requestReferenceSpace('viewer').then(viewerSpace => {
          session.requestHitTestSource({ space: viewerSpace }).then(source => {
            hitTestSource = source;
          });
        });
        session.addEventListener('end', () => {
          hitTestSourceRequested = false;
          hitTestSource = null;
        });
        hitTestSourceRequested = true;
      }

      if (hitTestSource) {
        const hitTestResults = frame.getHitTestResults(hitTestSource);
        if (hitTestResults.length > 0 && !isPlaced) {
          hasValidHit = true;
          const hit = hitTestResults[0];
          const pose = hit.getPose(refSpace);
          reticleGroup.matrix.fromArray(pose.transform.matrix);
          _tmpPos.setFromMatrixPosition(reticleGroup.matrix);
          _tmpQuat.setFromRotationMatrix(reticleGroup.matrix);
          arAnchorGroup.position.copy(_tmpPos);
          arAnchorGroup.quaternion.copy(_tmpQuat);
          arAnchorGroup.scale.setScalar(scaleFactor);
          arAnchorGroup.visible = true;
          reticleGroup.visible = showReticleVisual && !isPlaced;
        } else if (!isPlaced) {
          hasValidHit = false;
          arAnchorGroup.visible = false;
          reticleGroup.visible = false;
        }
      }
    }

    renderer.render(scene, camera);
  });

  return {
    toggleReticle: () => {
      showReticleVisual = !showReticleVisual;
      if (!isPlaced && hasValidHit) {
        reticleGroup.visible = showReticleVisual;
      }
      return showReticleVisual;
    },
    destroy: () => {
      isDestroyed = true;
      window.removeEventListener('resize', onWindowResize);
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.setAnimationLoop(null);
      if (splatWorker) splatWorker.terminate();
      if (splatViewer && splatViewer.dispose) splatViewer.dispose();
      renderer.dispose();
      try { container.removeChild(renderer.domElement); } catch (e) { }
      if (arButton.parentNode) arButton.parentNode.removeChild(arButton);
    }
  };
}
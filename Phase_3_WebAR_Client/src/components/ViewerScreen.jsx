import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Info, Target } from 'lucide-react';
import { createWebGLApp } from '../WebGLApp';
import DishInfoPanel from './DishInfoPanel';

export default function ViewerScreen({ dishId, onBack }) {
  const containerRef = useRef(null);
  const [dishData, setDishData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState('0%');
  const [error, setError] = useState(null);
  const [showInfo, setShowInfo] = useState(false);
  const [inAR, setInAR] = useState(false);
  const [isPlaced, setIsPlaced] = useState(false);
  const [reticleEnabled, setReticleEnabled] = useState(false);
  const [arStatus, setArStatus] = useState('Starting...');
  const webglAppRef = useRef(null);

  // Load dish data
  useEffect(() => {
    fetch('/assets/dishes.json')
      .then(res => res.json())
      .then(dishes => {
        const dish = dishes.find(d => d.id === dishId);
        if (dish) setDishData(dish);
        else setError('Dish not found');
      })
      .catch(err => setError(err.message));
  }, [dishId]);

  // Init WebGL when dishData is ready
  useEffect(() => {
    if (!dishData || !containerRef.current) return;

    const webglApp = createWebGLApp(containerRef.current, dishData, {
      onProgress: (pct) => setProgress(pct),
      onLoad: () => setLoading(false),
      onError: (err) => setError(err.message),
      onTap: () => setShowInfo(prev => !prev),
      onARStart: () => { setInAR(true); setIsPlaced(false); setArStatus('📱 Slowly scan a flat horizontal surface'); },
      onAREnd: () => { setInAR(false); setIsPlaced(false); },
      onARPlaced: () => { setArStatus(''); setIsPlaced(true); setShowInfo(true); },
    });
    
    webglAppRef.current = webglApp;

    return () => {
      webglApp.destroy();
      webglAppRef.current = null;
    };
  }, [dishData]);

  if (error) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center text-red-400 bg-[#0f0f13]">
        <p className="mb-4">{error}</p>
        <button onClick={onBack} className="px-6 py-2 bg-white/10 rounded-full text-white">Back to Menu</button>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
      className="absolute inset-0 w-full h-full bg-[#1a1a2e]"
    >
      {/* 3D Canvas Container */}
      <div ref={containerRef} className="absolute inset-0 w-full h-full" />

      {/* Top Floating Controls */}
      <div className="absolute top-6 left-6 right-6 flex justify-between z-10 pointer-events-none">
        <button 
          onClick={onBack}
          className="pointer-events-auto flex items-center gap-2 px-4 py-2 bg-black/40 backdrop-blur-xl border border-white/10 rounded-full text-white/90 hover:bg-black/60 transition-colors"
        >
          <ArrowLeft size={18} />
          <span>Menu</span>
        </button>
        {inAR && (
          <div className="flex gap-3">
            {!isPlaced && (
              <button 
                onClick={() => {
                  if (webglAppRef.current) {
                    setReticleEnabled(webglAppRef.current.toggleReticle());
                  }
                }}
                className={`pointer-events-auto w-10 h-10 flex items-center justify-center backdrop-blur-xl border border-white/10 rounded-full transition-colors ${reticleEnabled ? 'bg-[#00ff88]/20 text-[#00ff88]' : 'bg-black/40 text-white/90 hover:bg-black/60'}`}
              >
                <Target size={18} />
              </button>
            )}
            <button 
              onClick={() => setShowInfo(!showInfo)}
              className="pointer-events-auto w-10 h-10 flex items-center justify-center bg-black/40 backdrop-blur-xl border border-white/10 rounded-full text-white/90 hover:bg-black/60 transition-colors"
            >
              <Info size={18} />
            </button>
          </div>
        )}
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-[#0f0f13]/80 backdrop-blur-sm flex flex-col items-center justify-center z-50">
          <div className="spinner"></div>
          <p className="text-white/80 font-light tracking-wide">Preparing your dish… {progress}</p>
          {dishData?.pipeline && (
            <p className="text-xs text-white/40 uppercase tracking-[0.2em] mt-4">Pipeline: {dishData.pipeline}</p>
          )}
        </div>
      )}

      {/* AR Guidance Text */}
      {inAR && arStatus && (
        <div className="absolute bottom-32 left-1/2 -translate-x-1/2 px-6 py-3 bg-black/65 backdrop-blur-md border border-white/10 text-white text-sm rounded-full pointer-events-none z-10 text-center shadow-2xl transition-opacity">
          {arStatus}
        </div>
      )}

      {/* Dish Info Panel (AR only) */}
      {inAR && (
        <DishInfoPanel 
          dish={dishData} 
          isVisible={showInfo && !loading} 
          onClose={() => setShowInfo(false)} 
        />
      )}



    </motion.div>
  );
}

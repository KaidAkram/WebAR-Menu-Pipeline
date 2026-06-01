import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

export default function DishInfoPanel({ dish, isVisible, onClose }) {
  if (!dish) return null;

  return (
    <AnimatePresence>
      {isVisible && (
        <>
          {/* Backdrop for mobile */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="md:hidden absolute inset-0 bg-black/20 z-20 pointer-events-auto"
          />

          <motion.div
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute bottom-0 left-0 right-0 md:bottom-auto md:top-24 md:left-auto md:right-8 md:w-[400px] z-30 pointer-events-auto flex flex-col max-h-[85vh] md:max-h-[70vh]"
          >
            <div className="bg-white/10 backdrop-blur-2xl border border-white/20 rounded-t-3xl md:rounded-3xl shadow-2xl overflow-hidden flex flex-col">
              
              {/* Header */}
              <div className="flex justify-between items-start p-6 border-b border-white/10">
                <div>
                  <h2 className="text-3xl font-semibold text-white mb-1">{dish.name}</h2>
                  <div className="flex gap-4 text-sm font-medium">
                    <span className="text-[#00ff88]">{dish.price}</span>
                    <span className="text-white/60">{dish.calories}</span>
                  </div>
                </div>
                <button 
                  onClick={onClose}
                  className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Scrollable Content */}
              <div className="p-6 overflow-y-auto no-scrollbar">
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-2">Description</h3>
                  <p className="text-white/80 leading-relaxed font-light">
                    {dish.description}
                  </p>
                </div>
                
                {dish.ingredients && (
                  <div>
                    <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-2">Ingredients</h3>
                    <ul className="list-disc list-inside text-white/80 font-light space-y-1">
                      {dish.ingredients.map((ing, i) => (
                        <li key={i}>{ing}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

import React from 'react';
import { motion } from 'framer-motion';
import { Play } from 'lucide-react';

export default function DishCard({ dish, index, onClick }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 + 0.3, duration: 0.5 }}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="group relative flex flex-col bg-white/5 hover:bg-white/10 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden cursor-pointer transition-colors duration-300 shadow-2xl"
    >
      <div className="relative h-64 overflow-hidden">
        <img 
          src={`/assets/${dish.image}`} 
          alt={dish.name} 
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
          onError={(e) => { e.target.style.display = 'none'; }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent"></div>
        
        {dish.pipeline && (
          <div className="absolute top-4 right-4 px-3 py-1 bg-black/40 backdrop-blur-md rounded-full border border-white/10">
            <span className="text-xs font-mono text-white/80 uppercase tracking-wider">{dish.pipeline}</span>
          </div>
        )}

        <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end">
          <div>
            <h3 className="text-2xl font-medium text-white mb-1">{dish.name}</h3>
            <div className="flex gap-3 text-sm text-white/70">
              <span className="font-semibold text-[#00ff88]">{dish.price}</span>
              <span>•</span>
              <span>{dish.calories}</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 text-white group-hover:bg-white group-hover:text-black transition-colors">
            <Play size={18} className="ml-1" />
          </div>
        </div>
      </div>
      <div className="p-5 text-white/60 text-sm leading-relaxed line-clamp-2">
        {dish.description}
      </div>
    </motion.div>
  );
}

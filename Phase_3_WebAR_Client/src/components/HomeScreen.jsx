import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import DishCard from './DishCard';

export default function HomeScreen({ onSelectDish }) {
  const [dishes, setDishes] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/assets/dishes.json')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load menu');
        return res.json();
      })
      .then(setDishes)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="w-full h-full overflow-y-auto overflow-x-hidden no-scrollbar bg-gradient-to-b from-[#0f0f13] to-[#1a1a24] text-white"
    >
      <div className="max-w-6xl mx-auto px-6 py-12 md:py-20">
        <header className="mb-12 md:mb-20 text-center md:text-left">
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
          >
            <h1 className="text-4xl md:text-6xl font-semibold tracking-tight mb-4 text-transparent bg-clip-text bg-gradient-to-r from-white to-white/60">
              Gourmet AR Menu
            </h1>
            <p className="text-lg md:text-xl text-white/60 max-w-2xl font-light">
              Experience the future of dining. Preview ultra-realistic 3D dishes at true 1:1 scale in your own space before you order.
            </p>
          </motion.div>
        </header>

        {error ? (
          <div className="text-center text-red-400 py-20 bg-red-400/10 rounded-2xl border border-red-400/20 backdrop-blur-md">
            <p>{error}</p>
            <p className="text-sm opacity-70 mt-2">Ensure assets/dishes.json is accessible.</p>
          </div>
        ) : (
          <div>
            <h2 className="text-2xl font-medium mb-6 text-white/90">Featured Selection</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {dishes.map((dish, idx) => (
                <DishCard key={dish.id} dish={dish} index={idx} onClick={() => onSelectDish(dish.id)} />
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

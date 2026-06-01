import React, { useState, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import HomeScreen from './components/HomeScreen';
import ViewerScreen from './components/ViewerScreen';

export default function App() {
  const [selectedDishId, setSelectedDishId] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const dish = params.get('dish');
    if (dish) {
      setSelectedDishId(dish);
    }
  }, []);

  const handleSelectDish = (id) => {
    window.history.pushState({}, '', `?dish=${id}`);
    setSelectedDishId(id);
  };

  const handleBackToMenu = () => {
    window.history.pushState({}, '', window.location.pathname);
    setSelectedDishId(null);
  };

  return (
    <div className="w-full h-full relative overflow-hidden bg-[#0f0f13]">
      <AnimatePresence mode="wait">
        {!selectedDishId ? (
          <HomeScreen key="home" onSelectDish={handleSelectDish} />
        ) : (
          <ViewerScreen key="viewer" dishId={selectedDishId} onBack={handleBackToMenu} />
        )}
      </AnimatePresence>
    </div>
  );
}

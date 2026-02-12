import React, { useState, useEffect } from 'react';
import Slide1 from './slides/Slide1';
import Slide2 from './slides/Slide2';
import Slide3 from './slides/Slide3';
import Slide4 from './slides/Slide4';
import Slide5 from './slides/Slide5';
import Slide6 from './slides/SlideThree';
import Navigation from './Navigation';

const HeroSection: React.FC = () => {
  const [current, setCurrent] = useState(1);
  const [autoplay, setAutoplay] = useState(true);
  const total = 6;

  useEffect(() => {
    if (!autoplay) return;
    
    const interval = setInterval(() => {
      setCurrent(prev => (prev % total) + 1);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [autoplay, total]);

  const scheduleResume = (delay = 6000) => {
    setAutoplay(false);
    setTimeout(() => {
      setAutoplay(true);
    }, delay);
  };

  const handlePrev = () => {
    setCurrent(prev => Math.max(prev - 1, 1));
    scheduleResume();
  };

  const handleNext = () => {
    setCurrent(prev => Math.min(prev + 1, total));
    scheduleResume();
  };

  return (
    <section className="slide-hero min-h-screen flex items-center justify-center bg-gradient-to-b from-ntheemba-green-500 to-ntheemba-green-700 px-4">
      <div className="bg-white shadow-xl rounded-xl p-6 relative mx-auto hero-card">
        
        {/* Feature Label */}
        <div className="feature-label">
          Hello�� Welcome!😊
        </div>

        {/* Slides Container */}
        <div className="relative w-full h-full">
          {current === 1 && <Slide1 />}
          {current === 2 && <Slide2 />}
          {current === 3 && <Slide3 />}
          {current === 4 && <Slide4 />}
          {current === 5 && <Slide5 />}
          {current === 6 && <Slide6 />}
        </div>

        {/* Navigation */}
        <Navigation 
          current={current} 
          total={total} 
          onPrev={handlePrev} 
          onNext={handleNext} 
        />
      </div>
    </section>
  );
};

export default HeroSection;
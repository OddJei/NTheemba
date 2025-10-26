import React from 'react';
import phoneImg from '../../../assets/images/phonewhatsapp.png';

const Slide1: React.FC = () => {
  return (
    <div className="slide-item flex flex-col md:flex-row items-center gap-6 desktop-two-col w-full h-full overflow-auto">
      {/* Desktop layout (visible md and up) */}
      <div className="hidden md:flex md:flex-row md:items-center md:gap-6 w-full">
        <div className="md:flex-1 max-w-lg">
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-gray-900">Bomba Smart</h2>
          <p className="mt-3 text-base sm:text-lg md:text-xl text-gray-700">Serve customers, Save time — WhatsApp the easy way with NTheemba</p>
          <p className="mt-4 text-[13px] text-gray-600">NTheemba helps you respond faster, close more deals, and grow your business with ease.</p>
          <div className="mt-6">
            <a href="#" className="inline-block bg-ntheemba-orange-500 hover:bg-ntheemba-orange-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors">Start free</a>
          </div>
        </div>
        <div className="md:flex-1 flex justify-center">
          <img src={phoneImg} alt="Bomba Smart" className="w-44 md:w-72 lg:w-80 rounded-lg shadow hero-image bomba-desktop-image" />
        </div>
      </div>

      {/* Mobile layout (visible on small screens only) */}
      <div className="w-full flex flex-col items-center justify-center md:hidden">
        <div className="bomba-title">Bomba Smart</div>
  <div className="bomba-subtitle">Serve customers, Save time<br/>WhatsApp the easy Way<br/>na NTheemba</div>
        <img src={phoneImg} onError={(e) => {
          const target = e.target as HTMLImageElement;
          target.onerror = null;
          target.src = 'https://placehold.co/251x253';
        }} alt="Bomba Smart" className="bomba-img rounded-lg" />
  <div className="bomba-desc">NTheemba helps you respond faster, close more deals, and grow your business with ease.</div>
      </div>
    </div>
  );
};

export default Slide1;
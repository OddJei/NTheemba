import React from 'react';
import slide2Img from '../../../assets/images/slide2image.png';

const Slide2: React.FC = () => {
  return (
    <div className="slide-item flex flex-col md:flex-row items-center justify-center w-full h-full px-4 sm:px-6 md:px-8 py-6 overflow-auto relative gap-6">
      {/* Text left */}
      <div className="flex-1 flex flex-col justify-center items-start md:items-start z-10 max-w-md">
  <h3 className="soma-title text-xl sm:text-2xl md:text-3xl font-extrabold mb-4 font-poppins text-gray-900">Introducing NTheemba</h3>
        <div className="grid grid-cols-1 gap-4 mb-6 w-full">
          <div className="flex items-start gap-3 p-3 bg-white/10 rounded-xl backdrop-blur-sm border border-white/20">
            <span className="text-2xl mt-1">💬</span>
            <div>
              <h4 className="soma-subtitle font-bold text-sm text-gray-800 mb-1">Instant Replies</h4>
              <p className="text-xs text-gray-600 leading-relaxed">Instantly respond to customer questions so no inquiry goes unanswered — building trust and boosting satisfaction.</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-white/10 rounded-xl backdrop-blur-sm border border-white/20">
            <span className="text-2xl mt-1">📋</span>
            <div>
              <h4 className="soma-subtitle font-bold text-sm text-gray-800 mb-1">Take Orders Seamlessly</h4>
              <p className="text-xs text-gray-600 leading-relaxed">Let customers place and confirm orders without ever leaving WhatsApp.</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-white/10 rounded-xl backdrop-blur-sm border border-white/20">
            <span className="text-2xl mt-1">🛍️</span>
            <div>
              <h4 className="soma-subtitle font-bold text-sm text-gray-800 mb-1">Browse Your Catalog</h4>
              <p className="text-xs text-gray-600 leading-relaxed">Share an easy‑to‑navigate product catalog right in chat, so customers can explore and choose without leaving WhatsApp.</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-white/10 rounded-xl backdrop-blur-sm border border-white/20">
            <span className="text-2xl mt-1">💰</span>
            <div>
              <h4 className="soma-subtitle font-bold text-sm text-gray-800 mb-1">Mobile‑Money Payments</h4>
              <p className="text-xs text-gray-600 leading-relaxed">Accept Airtel Money, MTN, or Zamtel — quick, secure, and familiar.</p>
            </div>
          </div>
        </div>
      </div>
      {/* Image right */}
      <div className="flex-1 flex flex-col items-center z-10 pb-20 md:pb-4">
        <img 
          src={slide2Img}
          alt="Introducing NTheemba" 
          className="w-full max-w-xs md:max-w-sm rounded-3xl shadow-2xl border-4 border-white/20" 
        />
      </div>
    </div>
  );
};

export default Slide2;
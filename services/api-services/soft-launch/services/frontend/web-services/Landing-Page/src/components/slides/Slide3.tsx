import React from 'react';

const Slide3: React.FC = () => {
  return (
    <div className="slide-item flex flex-col items-center justify-center w-full h-full overflow-auto px-6 py-6 gap-6 mb-16 md:mb-0">
      {/* Header */}
      <div className="w-full text-center">
        <h3 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-gray-900 font-poppins">
          Why Use NTheemba
        </h3>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 w-full max-w-4xl">
        <div className="flex flex-col items-center text-center rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 p-6 shadow-lg hover:shadow-xl transition-all duration-300">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-blue-600 rounded-full flex items-center justify-center mb-4 shadow-lg">
            <span className="text-2xl">📱</span>
          </div>
          <p className="text-sm sm:text-base font-semibold text-gray-800 leading-relaxed">
            Zambia has <span className="font-bold text-blue-600">16.36 million</span> active mobile connections — over 80% of the population
          </p>
        </div>
        <div className="flex flex-col items-center text-center rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 p-6 shadow-lg hover:shadow-xl transition-all duration-300">
          <div className="w-16 h-16 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center mb-4 shadow-lg">
            <span className="text-2xl">📊</span>
          </div>
          <p className="text-sm sm:text-base font-semibold text-gray-800 leading-relaxed">
            Smartphone adoption is climbing fast, projected to hit <span className="font-bold text-green-600">4.14 million</span> units by 2030
          </p>
        </div>
        <div className="flex flex-col items-center text-center rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 p-6 shadow-lg hover:shadow-xl transition-all duration-300">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-400 to-purple-600 rounded-full flex items-center justify-center mb-4 shadow-lg">
            <span className="text-2xl">💬</span>
          </div>
          <p className="text-sm sm:text-base font-semibold text-gray-800 leading-relaxed">
            WhatsApp dominates Africa with usage rates above 90% among connected users in many markets
          </p>
        </div>
        <div className="flex flex-col items-center text-center rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20 p-6 shadow-lg hover:shadow-xl transition-all duration-300">
          <div className="w-16 h-16 bg-gradient-to-br from-yellow-400 to-yellow-600 rounded-full flex items-center justify-center mb-4 shadow-lg">
            <span className="text-2xl">💰</span>
          </div>
          <p className="text-sm sm:text-base font-semibold text-gray-800 leading-relaxed">
            Mobile money is booming — over <span className="font-bold text-yellow-600">843 million</span> transactions were processed in Zambia in 2021 alone
          </p>
        </div>
      </div>

      {/* Description */}
      <div className="w-full max-w-3xl text-center mt-6">
        <p className="text-base sm:text-lg italic text-gray-600 font-poppins">
          If your shop isn't on WhatsApp, you're missing the busiest marketplace in the country.
        </p>
      </div>
    </div>
  );
};

export default Slide3;
import React from 'react';

const SlideThree: React.FC = () => {
  return (
    <div className="slide-item flex flex-col md:flex-row items-center justify-center w-full h-full overflow-auto gap-6 px-4">
      {/* Image placeholder left */}
      <div className="flex-1 flex items-center justify-center mb-6 md:mb-0">
        <div className="w-48 h-48 md:w-64 md:h-64 bg-gray-200 rounded-2xl flex items-center justify-center border-2 border-dashed border-gray-400">
          <span className="text-gray-400 text-xl">Image Placeholder</span>
        </div>
      </div>
      {/* CTA content right */}
      <div className="flex-1 flex flex-col items-center justify-center text-center">
        <h4 className="text-lg md:text-xl text-gray-700 max-w-2xl mb-6 mt-8 text-left font-bold">Opportunities don't wait — and now, neither do your replies.</h4>
        <p className="text-lg md:text-xl text-gray-700 max-w-2xl mb-6 text-left">
          Join the movement of Zambian entrepreneurs using NTheemba to sell faster, serve better, and get paid without the headaches. Whether you run a stall, a shop, or a side hustle, NTheemba makes your business faster, smarter, and easier to manage.
        </p>
  <a href="#" className="inline-block bg-ntheemba-primary hover:bg-ntheemba-accent text-white font-semibold px-8 py-4 rounded-lg text-lg shadow-lg mt-4 transition-colors">Get Started with NTheemba</a>
      </div>
    </div>
  );
};

export default SlideThree;

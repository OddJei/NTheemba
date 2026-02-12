import React from 'react';

const Header: React.FC = () => {
  return (
    <header className="fixed top-0 left-0 w-full z-10 bg-transparent">
      <div className="max-w-screen-xl mx-auto flex justify-between items-center px-4 sm:px-6 py-3 sm:py-4">
        
        {/* Logo */}
        <div className="flex items-center space-x-2">
          <img 
            src="/ntheemba-logo-main.svg" 
            alt="NTheemba Logo" 
            className="h-8 w-8 sm:h-10 sm:w-10"
          />
          <div className="text-lg sm:text-xl md:text-2xl font-bold text-ntheemba-orange-500">NTheemba</div>
        </div>
        
        {/* Navigation */}
        <nav className="space-x-4 sm:space-x-6 text-xs sm:text-sm font-medium hidden md:flex text-white">
          <a href="#" className="hover:text-ntheemba-orange-500 transition-colors">Pricing</a>
          <a href="#" className="hover:text-ntheemba-orange-500 transition-colors">Resources</a>
          <a href="#" className="hover:text-ntheemba-orange-500 transition-colors">Contact Us</a>
        </nav>
        
        {/* Sign Up Button */}
        <button className="bg-ntheemba-orange-500 hover:bg-ntheemba-orange-600 text-white text-xs sm:text-sm px-3 sm:px-4 py-1.5 sm:py-2 rounded-md transition-colors font-semibold">
          Sign Up
        </button>
      </div>
    </header>
  );
};

export default Header;
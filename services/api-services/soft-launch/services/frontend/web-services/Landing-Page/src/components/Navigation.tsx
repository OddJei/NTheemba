interface NavigationProps {
  current: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}

const Navigation: React.FC<NavigationProps> = ({ current, total, onPrev, onNext }) => {
  return (
    <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex items-center space-x-4 z-50 pointer-events-auto">
      {/* Previous Button */}
      <button
        onClick={onPrev}
        className="w-10 h-10 rounded-full bg-ntheemba-orange-500 hover:bg-ntheemba-orange-600 text-white flex items-center justify-center transition-colors shadow-lg"
        aria-label="Previous slide"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* Slide Indicators */}
      <div className="flex space-x-2">
        {Array.from({ length: total }, (_, index) => (
          <button
            key={index + 1}
            className={`w-3 h-3 rounded-full transition-colors ${
              current === index + 1 ? 'bg-ntheemba-orange-500' : 'bg-gray-300'
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>

      {/* Next Button */}
      <button
        onClick={onNext}
        className="w-10 h-10 rounded-full bg-ntheemba-orange-500 hover:bg-ntheemba-orange-600 text-white flex items-center justify-center transition-colors shadow-lg"
        aria-label="Next slide"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
};

export default Navigation;
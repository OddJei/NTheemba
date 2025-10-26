import React from 'react';

const Slide5: React.FC = () => {
  return (
    <div className="slide-item flex flex-col md:flex-row items-center gap-6 desktop-two-col w-full h-full overflow-auto">
      <div className="md:flex-1 flex flex-col items-start justify-center w-full md:pr-8">
        {/* Local Roots, Global Vision */}
        <h3 className="mt-4 font-semibold">Local Roots, Global Vision</h3>
        <p className="mt-2 text-gray-600">
          NTheemba is dedicated to transforming the entrepreneurial landscape in Zambia. 
          Our mission is to empower micro, small, and medium enterprises through innovative 
          technology solutions. We believe in fostering local talent and driving economic 
          growth by making automation accessible to all.
        </p>
        {/* What Drives Us */}
        <p className="mt-4 font-semibold">What Drives Us</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
          <div className="p-3 rounded-lg bg-gray-50">
            <h4 className="font-bold block">Accessibility</h4>
            <span className="text-gray-700 text-sm">Works on the devices and networks you already have.</span>
          </div>
          <div className="p-3 rounded-lg bg-gray-50">
            <h4 className="font-bold block">Scalability</h4>
            <span className="text-gray-700 text-sm">Grows with you, from one stall to a full marketplace presence.</span>
          </div>
          <div className="p-3 rounded-lg bg-gray-50">
            <h4 className="font-bold block">Community Impact</h4>
            <span className="text-gray-700 text-sm">Every feature is built with MSME needs and customer trust in mind.</span>
          </div>
          <div className="p-3 rounded-lg bg-gray-50">
            <h4 className="font-bold block">Relevance</h4>
            <span className="text-gray-700 text-sm">Designed for the realities of doing business in Zambia and across Africa.</span>
          </div>
        </div>
      </div>
      <div className="md:flex-1 flex flex-col items-center">
        <h2 className="soma-title text-3xl md:text-4xl font-extrabold mb-4 mt-8">About Us</h2>
  <img src="./assets/images/about Us image.png" alt="About NTheemba" className="w-64 md:w-80 rounded-2xl object-cover mb-4" />
        <h3 className="mt-4 font-semibold">Why We Exist</h3>
  <p className="mt-2 text-gray-600">We've seen firsthand how many hardworking vendors, shopkeepers, and service providers run their entire business on mobile — yet still face barriers to speed, efficiency, and growth. NTheemba exists to remove those barriers, starting with NTheemba.</p>
      </div>
    </div>
  );
};

export default Slide5;
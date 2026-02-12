import React from 'react';

const Slide4: React.FC = () => {
  return (
    <div className="slide-item flex flex-col items-center justify-center gap-6 px-6 w-full h-full overflow-auto">
      {/* Heading */}
  <h3 className="text-2xl md:text-3xl font-extrabold">Using NTheemba</h3>
      <p className="text-center text-gray-600 max-w-2xl">
        Works with the number you already use — you're always in control, and so are your customers.
      </p>

      {/* Steps Grid */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-4xl">
        {/* Step 1 */}
        <div className="p-4 rounded-lg bg-gray-50 flex items-start gap-3">
          <span className="text-3xl">��</span>
          <div>
            <h4 className="font-bold text-lg">Step 1 — Say "Hello"</h4>
            <p className="text-gray-700 text-sm sm:text-base">
              Your customer sends a quick "Hello" to your WhatsApp number — that's all it takes for NTheemba to activate and start assisting.
            </p>
          </div>
        </div>

        {/* Step 2 */}
        <div className="p-4 rounded-lg bg-gray-50 flex items-start gap-3">
          <span className="text-3xl">��</span>
          <div>
            <h4 className="font-bold text-lg">Step 2 — NTheemba Responds</h4>
            <p className="text-gray-700 text-sm sm:text-base">
              Instant answers, product menus, and order guidance appear right in their chat.
            </p>
          </div>
        </div>

        {/* Step 3 */}
        <div className="p-4 rounded-lg bg-gray-50 flex items-start gap-3">
          <span className="text-3xl">��</span>
          <div>
            <h4 className="font-bold text-lg">Step 3 — Order & Pay</h4>
            <p className="text-gray-700 text-sm sm:text-base">
              Customers confirm their order and pay via Airtel, MTN, or Zamtel — all without leaving WhatsApp.
            </p>
          </div>
        </div>

        {/* Step 4 */}
        <div className="p-4 rounded-lg bg-gray-50 flex items-start gap-3">
          <span className="text-3xl">��</span>
          <div>
            <h4 className="font-bold text-lg">Step 4 — Say "Stop" Anytime</h4>
            <p className="text-gray-700 text-sm sm:text-base">
              If a customer wants to pause automation, they simply reply "Stop" and NTheemba steps back, letting you reply personally.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Slide4;
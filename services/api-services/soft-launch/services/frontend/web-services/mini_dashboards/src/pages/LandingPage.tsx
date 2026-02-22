// Landing page uses plain HTML buttons; remove unused imports

const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <section className="bg-[#FEF6ED] py-20">
        <div className="container mx-auto px-6 lg:px-20 text-center">
          <h1 className="text-4xl lg:text-5xl font-extrabold text-[#270A01] leading-tight">
            Chat‑Commerce Made Simple for MSMEs
          </h1>
          <p className="mt-6 text-lg text-[#035688] max-w-3xl mx-auto">
            NTheemba empowers Zambian and African MSMEs with automated catalogues, cart management,
            delivery orchestration, and transparent affiliate payouts — all through the chat channels
            they already use.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <a href="/onboarding/msme" className="inline-block">
              <button className="px-6 py-3 rounded-md bg-[#035688] text-white hover:bg-[#F38D1C] transition">
                Sign Up for Early Access
              </button>
            </a>

            <a href="/partner" className="inline-block">
              <button className="px-6 py-3 rounded-md border-2 border-[#C04208] text-[#C04208] hover:bg-[#C04208] hover:text-white transition">
                Partner with Us
              </button>
            </a>
          </div>
        </div>
      </section>

      {/* Problem Statement */}
      <section className="bg-white py-16">
        <div className="container mx-auto px-6 lg:px-20">
          <h2 className="text-2xl font-bold text-[#270A01]">The Problem</h2>
          <p className="mt-4 text-[#270A01] max-w-3xl">
            For most MSMEs, selling online still means posting on WhatsApp status and hoping someone calls. Orders get
            <span className="text-[#C04208] font-semibold"> lost orders</span>, payments are unreliable, and customers hesitate because
            <span className="text-[#C04208] font-semibold"> fragile trust</span>. Global platforms are too expensive, too
            complex, and not built for Zambia. Every day, entrepreneurs juggle manual records,
            <span className="text-[#C04208] font-semibold"> stalled growth</span> — when all they want is a simple, reliable way to sell and be paid fairly.
          </p>
        </div>
      </section>

      {/* Solution Statement */}
      <section className="bg-[#FEF6ED] py-16">
        <div className="container mx-auto px-6 lg:px-20">
          <h2 className="text-2xl font-bold text-[#270A01]">Our Solution</h2>
          <p className="mt-4 text-[#270A01] max-w-3xl">
            NTheemba solves this by turning everyday chats into commerce. MSMEs simply say ‘Hi’ to activate their bot instance.
            Customers browse products, place orders, and confirm payments — all inside WhatsApp, SMS, or mobile web. Delivery is
            verified with a shared code, and payouts are released instantly. Growth is automated, trackable, and fair — built for
            local realities, powered by community.
          </p>
        </div>
      </section>

      {/* Key Features */}
      <section className="bg-white py-16">
        <div className="container mx-auto px-6 lg:px-20">
          <h3 className="text-xl font-bold text-[#270A01]">Key Features</h3>
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              "Automated Catalogues",
              "Cart & Order Management",
              "Delivery Orchestration",
              "Affiliate Engine (10% revenue pool)",
              "Compliance & Transparency",
              "Trust & Credibility"
            ].map((f) => (
              <div key={f} className="p-6 border rounded-lg flex items-start gap-4">
                <div className="w-12 h-12 rounded-md flex items-center justify-center border-2 border-[#035688] text-[#035688]">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2v20M2 12h20" stroke="#035688" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                    <circle cx="18" cy="6" r="2" fill="#F38D1C" />
                  </svg>
                </div>
                <div>
                  <h4 className="font-semibold text-[#270A01]">{f}</h4>
                  <p className="text-sm text-[#035688] mt-1">Designed for local realities and easy setup.</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Community + Founder story */}
      <section className="bg-white py-16">
        <div className="container mx-auto px-6 lg:px-20 grid md:grid-cols-2 gap-8">
          <div>
            <h3 className="text-xl font-bold text-[#270A01]">Community Movement</h3>
            <p className="mt-4 text-[#270A01]">MSMEs don’t just join — they become part of a living network that promotes each other.</p>

            <hr className="my-6 border-[#C04208]" />

            <h3 className="text-xl font-bold text-[#270A01]">Fair Incentives</h3>
            <p className="mt-4 text-[#270A01]">Affiliates earn from platform revenue, not MSME margins.</p>
          </div>

          <div>
            <h3 className="text-xl font-bold text-[#270A01]">Founder Story</h3>
            <p className="mt-4 text-[#270A01]">Built in Zambia, by someone who lived MSME realities — from chef to software architect.</p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[#FEF6ED] py-12">
        <div className="container mx-auto px-6 lg:px-20 text-center">
          <h3 className="text-2xl font-bold text-[#270A01]">Ready to join the movement?</h3>
          <p className="mt-2 text-[#035688]">Sign up now to get early access and partner opportunities.</p>

          <div className="mt-6 flex items-center justify-center gap-4">
            <a href="/onboarding/msme">
              <button className="px-6 py-3 rounded-md bg-[#035688] text-white hover:bg-[#F38D1C] transition">Sign Up for Early Access</button>
            </a>
            <a href="mailto:jchisulokt@gmail.com">
              <button className="px-6 py-3 rounded-md border-2 border-[#C04208] text-[#C04208] hover:bg-[#C04208] hover:text-white transition">Partner with Us</button>
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#270A01] text-[#FEF6ED] py-8 mt-auto">
        <div className="container mx-auto px-6 lg:px-20 grid md:grid-cols-3 gap-6">
          <div>
            <h4 className="font-bold">NTheemba</h4>
            <p className="text-sm mt-2 text-[#FEF6ED]">NTheemba the company vs NTheemba the platform</p>
          </div>

          <div>
            <h4 className="font-semibold">Contact</h4>
            <p className="text-sm mt-2">jchisulokt@gmail.com | +260 961 086 845</p>
          </div>

          <div>
            <h4 className="font-semibold">Legal</h4>
            <p className="text-sm mt-2">
              <a href="/privacy" className="text-[#F38D1C] hover:text-[#C04208]">Privacy Policy</a> | <a href="/terms" className="text-[#F38D1C] hover:text-[#C04208]">Terms of Service</a>
            </p>
            <div className="mt-4">
              <a href="/how-it-works" className="text-[#F38D1C] hover:text-[#C04208] block">How NTheemba Works</a>
              <a href="/resources" className="text-[#F38D1C] hover:text-[#C04208] block mt-1">Resources</a>
              <a href="/pricing" className="text-[#F38D1C] hover:text-[#C04208] block mt-1">Pricing</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;

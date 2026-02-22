import React from "react";

const Step: React.FC<{icon: React.ReactNode; title: string; desc?: string}> = ({icon, title, desc}) => (
  <div className="flex items-start gap-4">
    <div className="w-14 h-14 flex items-center justify-center rounded-lg bg-white shadow-sm">{icon}</div>
    <div>
      <h4 className="font-semibold text-[#270A01]">{title}</h4>
      {desc && <p className="text-sm text-[#035688] mt-1">{desc}</p>}
    </div>
  </div>
);

const HowItWorks: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#FEF6ED] py-16">
      <div className="container mx-auto px-6 lg:px-20">
        <header className="text-center mb-8">
          <h1 className="text-3xl lg:text-4xl font-bold text-[#270A01]">How NTheemba Works — Simple, Fast, Reliable</h1>
        </header>

        <div className="grid md:grid-cols-2 gap-8 items-start">
          <div className="space-y-6">
            <Step
              icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" stroke="#035688" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              title={`1. Say "Hi" on WhatsApp`}
              desc={`Customers greet your business and instantly see your product list.`}
            />

            <Step
              icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="7" height="7" stroke="#F38D1C" strokeWidth="1.4"/><rect x="14" y="3" width="7" height="7" stroke="#F38D1C" strokeWidth="1.4"/><rect x="3" y="14" width="7" height="7" stroke="#F38D1C" strokeWidth="1.4"/><rect x="14" y="14" width="7" height="7" stroke="#F38D1C" strokeWidth="1.4"/></svg>}
              title={`2. Browse Your Catalog`}
              desc={`Products, prices, and categories displayed beautifully inside WhatsApp — no apps, no downloads.`}
            />

            <Step
              icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 6h15l-1 9H6z" stroke="#035688" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><circle cx="9" cy="20" r="1" fill="#035688"/><circle cx="18" cy="20" r="1" fill="#035688"/></svg>}
              title={`3. Place an Order`}
              desc={`Customers tap, choose quantity, and checkout effortlessly.`}
            />

            <Step
              icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 12h18" stroke="#C04208" strokeWidth="1.5" strokeLinecap="round"/><path d="M21 12l-3 3v-6l3 3z" fill="#C04208"/></svg>}
              title={`4. Smart Order Collection`}
              desc={`Bot guides delivery and payment options in a friendly flow.`}
            />

            <Step
              icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M13 2L3 14h9l-1 8 10-12h-9z" stroke="#F38D1C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              title={`5. Confirm & Receive Instantly`}
              desc={`Order summary shown, MSME gets customer details in real time.`}
            />

            <Step
              icon={<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2l3 5 5 2-3 5 1 6-6-3-6 3 1-6L4 9l5-2 3-5z" stroke="#035688" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              title={`6. Secure Delivery Confirmation`}
              desc={`Shared code ensures every order is verified before payout is released.`}
            />
          </div>

          <aside className="bg-white p-6 rounded-lg shadow-md">
            <h3 className="text-xl font-bold text-[#270A01]">Affiliate Promotion</h3>
            <p className="mt-3 text-[#270A01]">Affiliates share your products across Facebook, WhatsApp, TikTok, and Instagram. Customers click → land directly in your WhatsApp shop → you receive the order instantly.</p>

            <div className="mt-4 text-[#C04208] space-y-2">
              <div>• Zero marketing cost</div>
              <div>• More reach</div>
              <div>• More sales</div>
              <div>• More visibility</div>
              <div>• Affiliates earn from the platform, not from you</div>
            </div>

            <hr className="my-6 border-[#C04208]" />

            <h4 className="font-semibold text-[#270A01]">Timeline</h4>
            <div className="mt-3">
              <div className="relative h-24">
                <div className="absolute left-6 top-3 h-px w-full bg-[#C04208]" />
                <div className="absolute left-6 top-0">
                  <div className="w-3 h-3 rounded-full bg-[#F38D1C]" />
                </div>
                <div className="absolute left-1/3 top-6">
                  <div className="w-3 h-3 rounded-full bg-[#F38D1C]" />
                </div>
                <div className="absolute left-2/3 top-12">
                  <div className="w-3 h-3 rounded-full bg-[#F38D1C]" />
                </div>
              </div>

              <div className="space-y-2 text-sm text-[#270A01]">
                <div><strong>Early Access (Now – Jan)</strong>: Free setup, product list configured, priority onboarding, early affiliate exposure.</div>
                <div><strong>Soft Launch (Feb/March 2026)</strong>: Real orders, real payouts, hands‑on support.</div>
                <div><strong>Public Launch</strong>: (3 months later) Dashboards, automation, analytics, more growth tools.</div>
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <a href="/login" className="inline-block">
                <button className="px-4 py-2 rounded-md bg-[#035688] text-white hover:bg-[#F38D1C] transition">See the Bot in Action</button>
              </a>
              <a href="/onboarding/msme" className="inline-block">
                <button className="px-4 py-2 rounded-md border-2 border-[#C04208] text-[#C04208] hover:bg-[#C04208] hover:text-white transition">Join Early Access</button>
              </a>
            </div>

          </aside>
        </div>
      </div>
    </div>
  );
};

export default HowItWorks;

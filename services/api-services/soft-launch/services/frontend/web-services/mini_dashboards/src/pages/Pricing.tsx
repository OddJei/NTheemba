import React from "react";
import { Button } from "@/components/ui/button";

const Pricing: React.FC = () => {
  const tiers = [
    { name: "Early Access", price: "Free", bullets: ["Free setup", "Priority onboarding", "Early affiliate exposure"] },
    { name: "Soft Launch", price: "ZMW 49/mo", bullets: ["Orders & payouts", "Basic analytics", "Hands-on support"] },
    { name: "Scale", price: "Contact Us", bullets: ["Advanced dashboards", "Custom integrations", "Dedicated success manager"] }
  ];

  return (
    <div className="min-h-screen bg-[#FEF6ED] py-16">
      <div className="container mx-auto px-6 lg:px-20">
        <h1 className="text-3xl font-bold text-[#270A01]">Pricing</h1>
        <p className="mt-3 text-[#035688] max-w-2xl">Simple, transparent pricing designed for MSMEs.</p>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map(t => (
            <div key={t.name} className="p-6 border rounded-lg bg-white">
              <h3 className="text-xl font-semibold text-[#270A01]">{t.name}</h3>
              <p className="text-2xl font-bold text-[#035688] mt-2">{t.price}</p>
              <ul className="mt-4 list-disc list-inside text-[#270A01]">
                {t.bullets.map(b => <li key={b}>{b}</li>)}
              </ul>
              <div className="mt-6">
                <Button className="bg-[#035688] hover:bg-[#F38D1C] text-white">Choose</Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Pricing;

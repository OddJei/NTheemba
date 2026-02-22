import React from "react";
import { Button } from "@/components/ui/button";

const Resources: React.FC = () => {
  const resources = [
    { title: "Getting Started Guide", desc: "Step-by-step setup for your WhatsApp shop.", href: "/resources/getting-started" },
    { title: "FAQ for MSMEs", desc: "Answers to common questions about selling and payouts.", href: "/resources/faq" },
    { title: "Affiliate Guide", desc: "How affiliates can share and earn on NTheemba.", href: "/resources/affiliate-guide" },
    { title: "API Docs", desc: "Developer documentation for integrations.", href: "/resources/api" }
  ];

  return (
    <div className="min-h-screen bg-[#FEF6ED] py-16">
      <div className="container mx-auto px-6 lg:px-20">
        <h1 className="text-3xl font-bold text-[#270A01]">Resources</h1>
        <p className="mt-3 text-[#035688] max-w-2xl">Guides, FAQs, and documentation to help you get the most from NTheemba.</p>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-6">
          {resources.map(r => (
            <div key={r.title} className="p-6 bg-white border rounded-lg">
              <h3 className="text-lg font-semibold text-[#270A01]">{r.title}</h3>
              <p className="text-sm text-[#035688] mt-2">{r.desc}</p>
              <div className="mt-4">
                <a href={r.href}>
                  <Button className="bg-[#035688] hover:bg-[#F38D1C] text-white">Open</Button>
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Resources;

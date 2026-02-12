import { Routes, Route } from "react-router-dom";
import MSMEDashboard from "@/pages/msme/Dashboard";
import MSMEProducts from "@/pages/msme/Products";
import MSMEBranding from "@/pages/msme/Branding";
import MSMEInsights from "@/pages/msme/Insights";
import MSMECampaigns from "@/pages/msme/Campaigns";
import MSMESubscriptionPlans from "@/pages/msme/SubscriptionPlans";
import MSMESubscription from "@/pages/msme/Subscription";
import MSMELayout from "@/components/layouts/MSMELayout";
import UbuntuCommunity from "@/pages/UbuntuCommunity";
import UbuntuSubscriptionPlans from "@/pages/UbuntuSubscriptionPlans";

const MSMERoutes = () => {
  return (
    <MSMELayout>
      <Routes>
        <Route path="/" element={<MSMEDashboard />} />
        <Route path="/products" element={<MSMEProducts />} />
        <Route path="/branding" element={<MSMEBranding />} />
        <Route path="/insights" element={<MSMEInsights />} />
        <Route path="/campaigns" element={<MSMECampaigns />} />
        <Route path="/subscription-plans" element={<MSMESubscriptionPlans />} />
        <Route path="/subscription" element={<MSMESubscription />} />
        <Route path="/ubuntu-community" element={<UbuntuCommunity />} />
        <Route path="/ubuntu-subscription" element={<UbuntuSubscriptionPlans />} />
      </Routes>
    </MSMELayout>
  );
};

export default MSMERoutes;
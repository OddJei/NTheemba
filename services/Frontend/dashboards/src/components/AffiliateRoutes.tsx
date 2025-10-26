import { Routes, Route } from "react-router-dom";
import AffiliateDashboard from "@/pages/affiliate/Dashboard";
import AffiliateCampaigns from "@/pages/affiliate/Campaigns";
import AffiliateContent from "@/pages/affiliate/Content";
import AffiliateEarnings from "@/pages/affiliate/Earnings";
import AffiliateLeaderboards from "@/pages/affiliate/Leaderboards";
import AffiliateProfile from "@/pages/affiliate/Profile";
import LinkGenerator from "@/pages/affiliate/LinkGenerator";
import AffiliatePayouts from "@/pages/affiliate/Payouts";
import AffiliateNotifications from "@/pages/affiliate/Notifications";
import AffiliateSecurity from "@/pages/affiliate/Security";
import AffiliateFeedback from "@/pages/affiliate/Feedback";
import AffiliateSubscriptionPlans from "@/pages/affiliate/SubscriptionPlans";
import AffiliateSubscription from "@/pages/affiliate/Subscription";
import AffiliateLayout from "@/components/layouts/AffiliateLayout";
import UbuntuCommunity from "@/pages/UbuntuCommunity";
import UbuntuSubscriptionPlans from "@/pages/UbuntuSubscriptionPlans";

const AffiliateRoutes = () => {
  return (
    <AffiliateLayout>
      <Routes>
        <Route path="/" element={<AffiliateDashboard />} />
        <Route path="/campaigns" element={<AffiliateCampaigns />} />
        <Route path="/content" element={<AffiliateContent />} />
        <Route path="/earnings" element={<AffiliateEarnings />} />
        <Route path="/leaderboards" element={<AffiliateLeaderboards />} />
        <Route path="/profile" element={<AffiliateProfile />} />
        <Route path="/links" element={<LinkGenerator />} />
        <Route path="/payouts" element={<AffiliatePayouts />} />
        <Route path="/notifications" element={<AffiliateNotifications />} />
        <Route path="/security" element={<AffiliateSecurity />} />
        <Route path="/subscription-plans" element={<AffiliateSubscriptionPlans />} />
        <Route path="/subscription" element={<AffiliateSubscription />} />
        <Route path="/feedback" element={<AffiliateFeedback />} />
        <Route path="/ubuntu-community" element={<UbuntuCommunity />} />
        <Route path="/ubuntu-subscription" element={<UbuntuSubscriptionPlans />} />
      </Routes>
    </AffiliateLayout>
  );
};

export default AffiliateRoutes;
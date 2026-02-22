import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from './lib/authContext';
import Landing from './pages/Landing';
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import AffiliateDashboard from './pages/AffiliateDashboard';
import MSMEDashboard from './pages/MSMEDashboard';
import AdminDashboard from './pages/AdminDashboard';
import HowItWorks from './pages/HowItWorks';
import Resources from './pages/Resources';
import Pricing from './pages/Pricing';
import OnboardingMSME from './pages/OnboardingMSME';
import OnboardingAffiliate from './pages/OnboardingAffiliate';
import OnboardingCustomer from './pages/OnboardingCustomer';
import Terms from './pages/Terms';
import Privacy from './pages/Privacy';

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/affiliate" element={<AffiliateDashboard />} />
          <Route path="/msme" element={<MSMEDashboard />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/onboarding/msme" element={<OnboardingMSME />} />
          <Route path="/onboarding/affiliate" element={<OnboardingAffiliate />} />
          <Route path="/onboarding/customer" element={<OnboardingCustomer />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/landing-page" element={<LandingPage />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Login from "./pages/Login";
import AuthWatcher from "./components/AuthWatcher";
import { AuthProvider } from './lib/authContext';
import MSMERoutes from "./components/MSMERoutes";
import AffiliateRoutes from "./components/AffiliateRoutes";
import UbuntuCommunity from "./pages/UbuntuCommunity";
import UbuntuSubscriptionPlans from "./pages/UbuntuSubscriptionPlans";
import SubscriptionDemo from "./pages/SubscriptionDemo";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <AuthProvider>
        <BrowserRouter>
  <AuthWatcher />
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/login" element={<Login />} />
          <Route path="/ubuntu-community" element={<UbuntuCommunity />} />
          <Route path="/ubuntu-subscription" element={<UbuntuSubscriptionPlans />} />
          <Route path="/subscription-demo" element={<SubscriptionDemo />} />
          <Route path="/msme/*" element={<MSMERoutes />} />
          <Route path="/affiliate/*" element={<AffiliateRoutes />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
        </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

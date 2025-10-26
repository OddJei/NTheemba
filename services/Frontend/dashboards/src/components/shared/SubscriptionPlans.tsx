import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import BillingPayment from './BillingPayment';
import { 
  Crown, 
  Zap, 
  Check, 
  Star,
  Users,
  TrendingUp,
  Gift,
  Shield,
  Headphones,
  ArrowRight,
  DollarSign,
  Target
} from "lucide-react";

interface SubscriptionPlansProps {
  userType: 'msme' | 'affiliate';
  currentPlan?: string;
  onPlanSelect?: (planId: string, billing: 'monthly' | 'yearly') => void;
}

const SubscriptionPlans: React.FC<SubscriptionPlansProps> = ({ 
  userType, 
  currentPlan = 'free',
  onPlanSelect 
}) => {
  const [isYearly, setIsYearly] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<{planId: string, billingCycle: 'monthly' | 'yearly', amount: number, planName: string} | null>(null);

  const msmePlans = [
    {
      id: 'pro',
      name: 'Pro',
      subtitle: 'For Growing MSMEs',
      price: { monthly: 50, yearly: 500 },
      color: 'from-blue-500 to-purple-500',
      icon: <TrendingUp className="w-6 h-6" />,
      popular: true,
      description: 'Perfect for small & growth-stage MSMEs ready to scale',
      features: [
        'SUBDS Campaign Tools',
        'ZMW 1.50 commission per affiliate sale',
        'Advanced Analytics Dashboard',
        'Priority Customer Support',
        'WhatsApp Business Integration',
        'Product Bundle Creation',
        'Cross-Promotion Tools',
        'Monthly Performance Reports'
      ],
      trial: '14-day free trial OR ZMW 10 first month',
      targetAudience: 'Small & growth-stage MSMEs'
    },
    {
      id: 'elite',
      name: 'Elite',
      subtitle: 'For High-Volume MSMEs',
      price: { monthly: 150, yearly: 1500 },
      color: 'from-yellow-500 to-orange-500',
      icon: <Crown className="w-6 h-6" />,
      popular: false,
      description: 'Invite-only tier for high-volume MSMEs & B2B partners',
      features: [
        'All Pro Features',
        'ZMW 2.00 commission per affiliate sale',
        'Dedicated Account Manager',
        'Custom Campaign Design',
        'API Access for Integration',
        'White-label Solutions',
        'Priority Product Listings',
        'Exclusive B2B Networks',
        'Advanced Revenue Sharing'
      ],
      trial: '30-day free trial (invite-only)',
      targetAudience: 'High-volume MSMEs & B2B partners'
    }
  ];

  const affiliatePlans = [
    {
      id: 'basic',
      name: 'Basic',
      subtitle: 'Free Forever',
      price: { monthly: 0, yearly: 0 },
      color: 'from-green-500 to-blue-500',
      icon: <Users className="w-6 h-6" />,
      popular: false,
      description: 'Start your affiliate journey with no upfront costs',
      features: [
        'ZMW 1.00 commission per sale',
        'Basic referral links',
        'Monthly payouts (min ZMW 50)',
        'Standard support',
        'Access to product catalog',
        'Performance tracking',
        'Training materials'
      ],
      trial: 'Join instantly',
      targetAudience: 'New affiliates'
    },
    {
      id: 'pro',
      name: 'Pro',
      subtitle: 'For Serious Affiliates',
      price: { monthly: 50, yearly: 500 },
      color: 'from-purple-500 to-pink-500',
      icon: <Star className="w-6 h-6" />,
      popular: true,
      description: 'Higher commissions and priority access for committed affiliates',
      features: [
        'ZMW 1.50 commission per sale',
        'Bi-weekly payouts (min ZMW 30)',
        'Premium marketing materials',
        'Product launch previews',
        'Recruitment commissions (5% override)',
        'Content creation rewards',
        'Performance bonuses',
        'Priority support'
      ],
      trial: '14-day free trial',
      targetAudience: 'Active affiliates'
    }
  ];

  const plans = userType === 'msme' ? msmePlans : affiliatePlans;

  const getPrice = (plan: typeof plans[0]) => {
    const price = isYearly ? plan.price.yearly : plan.price.monthly;
    const period = isYearly ? 'year' : 'month';
    return { price, period };
  };

  const getSavings = (plan: typeof plans[0]) => {
    if (plan.price.yearly === 0) return null;
    const monthlyTotal = plan.price.monthly * 12;
    const yearlyPrice = plan.price.yearly;
    const savings = monthlyTotal - yearlyPrice;
    const percentage = Math.round((savings / monthlyTotal) * 100);
    return { amount: savings, percentage };
  };

  const handlePlanSelect = (planId: string) => {
    const plan = plans.find(p => p.id === planId);
    if (!plan) return;

    const { price } = getPrice(plan);
    const billingCycle = isYearly ? 'yearly' : 'monthly';

    if (price === 0) {
      // Free plan - no payment needed
      if (onPlanSelect) {
        onPlanSelect(planId, billingCycle);
      }
    } else {
      // Paid plan - show billing
      setSelectedPlan({
        planId,
        billingCycle,
        amount: price,
        planName: plan.name
      });
      setShowBilling(true);
    }
  };

  const handlePaymentSuccess = () => {
    if (selectedPlan && onPlanSelect) {
      onPlanSelect(selectedPlan.planId, selectedPlan.billingCycle);
    }
    setShowBilling(false);
    setSelectedPlan(null);
  };

  const handleBackFromBilling = () => {
    setShowBilling(false);
    setSelectedPlan(null);
  };

  if (showBilling && selectedPlan) {
    return (
      <BillingPayment
        planName={selectedPlan.planName}
        amount={selectedPlan.amount}
        billingCycle={selectedPlan.billingCycle}
        onBack={handleBackFromBilling}
        onPaymentSuccess={handlePaymentSuccess}
      />
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-3 sm:space-y-4">
        <div className="flex items-center justify-center space-x-2 sm:space-x-3">
          {userType === 'msme' ? (
            <TrendingUp className="w-6 h-6 sm:w-8 sm:h-8 text-blue-600" />
          ) : (
            <Target className="w-6 h-6 sm:w-8 sm:h-8 text-purple-600" />
          )}
          <h1 className="text-2xl sm:text-3xl font-bold">
            {userType === 'msme' ? 'MSME' : 'Affiliate'} Subscription Plans
          </h1>
        </div>
        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto px-4">
          {userType === 'msme' 
            ? 'Choose the right plan to grow your business with enhanced tools and higher commissions'
            : 'Select your affiliate tier to unlock higher commissions and exclusive benefits'
          }
        </p>
        
        {/* Billing Toggle */}
        {plans.some(plan => plan.price.yearly > 0) && (
          <div className="flex items-center justify-center space-x-2 sm:space-x-4 bg-muted p-2 rounded-lg w-fit mx-auto">
            <span className={`text-xs sm:text-sm ${!isYearly ? 'font-semibold' : 'text-muted-foreground'}`}>Monthly</span>
            <Switch checked={isYearly} onCheckedChange={setIsYearly} />
            <span className={`text-xs sm:text-sm ${isYearly ? 'font-semibold' : 'text-muted-foreground'}`}>Yearly</span>
            <Badge className="bg-green-100 text-green-800 ml-2 text-xs">Save up to 17%</Badge>
          </div>
        )}
      </div>

      {/* Subscription Plans */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
        {plans.map((plan) => {
          const { price, period } = getPrice(plan);
          const savings = getSavings(plan);
          const isCurrentPlan = currentPlan === plan.id;
          
          return (
            <Card 
              key={plan.id} 
              className={`relative ${
                plan.popular ? 'ring-2 ring-blue-500 transform scale-[1.02] sm:scale-105' : ''
              } ${isCurrentPlan ? 'ring-2 ring-green-500' : ''} hover:shadow-md transition-all`}
            >
              {plan.popular && (
                <div className="absolute -top-2 sm:-top-3 left-1/2 transform -translate-x-1/2">
                  <Badge className="bg-blue-500 text-white px-2 py-1 sm:px-4 sm:py-1 text-xs">Most Popular</Badge>
                </div>
              )}

              {isCurrentPlan && (
                <div className="absolute -top-2 sm:-top-3 right-4">
                  <Badge className="bg-green-500 text-white px-2 py-1 text-xs">Current Plan</Badge>
                </div>
              )}
              
              <CardHeader className="text-center pb-3 sm:pb-6">
                <div className={`w-12 h-12 sm:w-16 sm:h-16 mx-auto rounded-full bg-gradient-to-r ${plan.color} flex items-center justify-center text-white mb-3 sm:mb-4`}>
                  {plan.icon}
                </div>
                <CardTitle className="text-lg sm:text-xl">{plan.name}</CardTitle>
                <CardDescription className="text-sm">{plan.description}</CardDescription>
                
                <div className="space-y-2">
                  <div className="text-2xl sm:text-3xl font-bold">
                    {price === 0 ? 'Free' : `ZMW ${price.toLocaleString()}`}
                    {price > 0 && <span className="text-base sm:text-lg text-muted-foreground">/{period}</span>}
                  </div>
                  {savings && isYearly && (
                    <Badge variant="secondary" className="bg-green-100 text-green-800 text-xs">
                      Save ZMW {savings.amount} ({savings.percentage}%)
                    </Badge>
                  )}
                  <div className="text-xs sm:text-sm text-muted-foreground">
                    {plan.trial}
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="space-y-3 sm:space-y-4 px-3 sm:px-6">
                <div className="space-y-2">
                  {plan.features.map((feature, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <Check className="w-3 h-3 sm:w-4 sm:h-4 text-green-500 flex-shrink-0" />
                      <span className="text-xs sm:text-sm">{feature}</span>
                    </div>
                  ))}
                </div>
                
                <div className="border-t pt-3 sm:pt-4">
                  <p className="text-xs text-muted-foreground mb-2">Target Audience:</p>
                  <p className="text-xs sm:text-sm font-medium">{plan.targetAudience}</p>
                </div>
                
                <Button 
                  className={`w-full py-2 sm:py-3 text-sm sm:text-base ${
                    plan.popular ? `bg-gradient-to-r ${plan.color} hover:opacity-90` : ''
                  } ${isCurrentPlan ? 'bg-green-600 hover:bg-green-700' : ''}`}
                  variant={plan.popular ? "default" : isCurrentPlan ? "default" : "outline"}
                  onClick={() => handlePlanSelect(plan.id)}
                  disabled={isCurrentPlan}
                >
                  {isCurrentPlan ? 'Current Plan' : plan.id === 'basic' ? 'Start Free' : 'Upgrade Now'}
                  {!isCurrentPlan && <ArrowRight className="w-3 h-3 sm:w-4 sm:h-4 ml-2" />}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Benefits Summary */}
      <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
        <CardContent className="p-4 sm:p-6">
          <div className="text-center space-y-3 sm:space-y-4">
            <h3 className="text-xl sm:text-2xl font-bold">Why Choose {userType === 'msme' ? 'NTheemba MSME' : 'NTheemba Affiliate'}?</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 mt-4">
              <div className="text-center space-y-2">
                <div className="w-12 h-12 mx-auto bg-blue-100 rounded-full flex items-center justify-center">
                  <Shield className="w-6 h-6 text-blue-600" />
                </div>
                <h4 className="font-semibold text-sm sm:text-base">Secure & Reliable</h4>
                <p className="text-xs sm:text-sm text-muted-foreground">Bank-level security with guaranteed payouts</p>
              </div>
              <div className="text-center space-y-2">
                <div className="w-12 h-12 mx-auto bg-green-100 rounded-full flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-green-600" />
                </div>
                <h4 className="font-semibold text-sm sm:text-base">Growth Focused</h4>
                <p className="text-xs sm:text-sm text-muted-foreground">Tools and insights to maximize your earnings</p>
              </div>
              <div className="text-center space-y-2 sm:col-span-2 lg:col-span-1">
                <div className="w-12 h-12 mx-auto bg-purple-100 rounded-full flex items-center justify-center">
                  <Headphones className="w-6 h-6 text-purple-600" />
                </div>
                <h4 className="font-semibold text-sm sm:text-base">Expert Support</h4>
                <p className="text-xs sm:text-sm text-muted-foreground">Dedicated support team to help you succeed</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SubscriptionPlans;

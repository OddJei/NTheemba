import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { 
  Check, 
  X, 
  Crown, 
  Star, 
  Zap,
  Shield,
  TrendingUp,
  Users,
  BarChart3,
  Smartphone,
  CreditCard,
  HeadphonesIcon,
  Award,
  ArrowRight
} from 'lucide-react';

interface PlanFeature {
  name: string;
  pro: boolean | string;
  proPlus: boolean | string;
}

const MSMESubscriptionPlans = () => {
  const [isYearly, setIsYearly] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<'pro' | 'pro-plus' | null>(null);

  const pricing = {
    pro: {
      monthly: 299,
      yearly: 2990, // ~2 months free
    },
    proPlus: {
      monthly: 599,
      yearly: 5990, // ~2 months free
    }
  };

  const features: PlanFeature[] = [
    {
      name: 'MSME Control Center',
      pro: true,
      proPlus: true
    },
    {
      name: 'Product Catalog Management',
      pro: true,
      proPlus: true
    },
    {
      name: 'Order & Customer Management',
      pro: true,
      proPlus: true
    },
    {
      name: 'Multi-Branch Support',
      pro: false,
      proPlus: true
    },
    {
      name: 'Advanced Inventory Management',
      pro: 'Basic',
      proPlus: 'Batch tracking, low-stock alerts'
    },
    {
      name: 'SUBDS Campaigns',
      pro: true,
      proPlus: true
    },
    {
      name: 'QR/Link Generation',
      pro: true,
      proPlus: true
    },
    {
      name: 'Analytics & Reports',
      pro: 'Basic',
      proPlus: 'Advanced with funnel analysis'
    },
    {
      name: 'Audience Targeting',
      pro: false,
      proPlus: true
    },
    {
      name: 'A/B Testing',
      pro: false,
      proPlus: true
    },
    {
      name: 'Priority Marketplace Placement',
      pro: false,
      proPlus: true
    },
    {
      name: 'Payment Methods',
      pro: 'Mobile money, card, bank',
      proPlus: 'All Pro + multi-currency'
    },
    {
      name: 'Payout Frequency',
      pro: 'Monthly',
      proPlus: 'Weekly + priority processing'
    },
    {
      name: 'Real-time Dashboards',
      pro: true,
      proPlus: true
    },
    {
      name: 'Custom Reports',
      pro: false,
      proPlus: true
    },
    {
      name: 'Performance Reviews',
      pro: 'Monthly',
      proPlus: 'Quarterly + dedicated insights'
    },
    {
      name: 'Affiliate Network Access',
      pro: 'Standard',
      proPlus: 'Invite-only partners + boosted incentives'
    },
    {
      name: 'Support Level',
      pro: 'Help center, chat/email',
      proPlus: 'Dedicated account manager + hotline'
    },
    {
      name: 'Training & Onboarding',
      pro: 'Standard modules',
      proPlus: 'Elite training + priority onboarding'
    },
    {
      name: 'Branding & Themes',
      pro: 'Basic storefront SEO',
      proPlus: 'Premium themes + featured badge'
    }
  ];

  const renderFeatureValue = (value: boolean | string) => {
    if (value === true) {
      return <Check className="w-5 h-5 text-green-600" />;
    }
    if (value === false) {
      return <X className="w-5 h-5 text-gray-400" />;
    }
    return <span className="text-sm text-gray-600">{value}</span>;
  };

  const handleUpgrade = (plan: 'pro' | 'pro-plus') => {
    setSelectedPlan(plan);
    // Here you would integrate with payment processor
    console.log(`Upgrading to ${plan} plan (${isYearly ? 'yearly' : 'monthly'})`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Choose Your MSME Plan
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Scale your business with our comprehensive suite of tools
          </p>
          
          {/* Billing Toggle */}
          <div className="flex items-center justify-center space-x-4">
            <span className={`font-medium ${!isYearly ? 'text-blue-600' : 'text-gray-500'}`}>
              Monthly
            </span>
            <Switch 
              checked={isYearly} 
              onCheckedChange={setIsYearly}
            />
            <span className={`font-medium ${isYearly ? 'text-blue-600' : 'text-gray-500'}`}>
              Yearly
            </span>
            {isYearly && (
              <Badge variant="secondary" className="bg-green-100 text-green-800">
                Save 17%
              </Badge>
            )}
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 mb-12">
          {/* Pro Plan */}
          <Card className="relative border-2 border-blue-200 hover:border-blue-300 transition-colors">
            <CardHeader className="text-center pb-8">
              <div className="mx-auto w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
                <Star className="w-8 h-8 text-blue-600" />
              </div>
              <CardTitle className="text-2xl font-bold">Pro Tier</CardTitle>
              <div className="text-4xl font-bold text-blue-600 mb-2">
                ZMW {isYearly ? pricing.pro.yearly : pricing.pro.monthly}
                <span className="text-lg text-gray-500 font-normal">
                  /{isYearly ? 'year' : 'month'}
                </span>
              </div>
              <p className="text-gray-600">Perfect for growing MSMEs</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Complete MSME Control Center</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>SUBDS Campaigns & Analytics</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Monthly Payouts</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Affiliate Network Access</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Email & Chat Support</span>
                </li>
              </ul>
              <Button 
                className="w-full" 
                onClick={() => handleUpgrade('pro')}
                disabled={selectedPlan === 'pro'}
              >
                {selectedPlan === 'pro' ? 'Processing...' : 'Start Pro Plan'}
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>

          {/* Pro+ Plan */}
          <Card className="relative border-2 border-purple-200 hover:border-purple-300 transition-colors">
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <Badge className="bg-gradient-to-r from-purple-600 to-pink-600 text-white px-4 py-1">
                <Crown className="w-4 h-4 mr-1" />
                RECOMMENDED
              </Badge>
            </div>
            <CardHeader className="text-center pb-8 pt-8">
              <div className="mx-auto w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center mb-4">
                <Crown className="w-8 h-8 text-white" />
              </div>
              <CardTitle className="text-2xl font-bold">Pro+ Tier</CardTitle>
              <div className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent mb-2">
                ZMW {isYearly ? pricing.proPlus.yearly : pricing.proPlus.monthly}
                <span className="text-lg text-gray-500 font-normal">
                  /{isYearly ? 'year' : 'month'}
                </span>
              </div>
              <p className="text-gray-600">For ambitious enterprises</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="font-medium">Everything in Pro, plus:</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Zap className="w-5 h-5 text-purple-600" />
                  <span>Multi-Branch Support</span>
                </li>
                <li className="flex items-center space-x-3">
                  <BarChart3 className="w-5 h-5 text-purple-600" />
                  <span>Advanced Analytics & A/B Testing</span>
                </li>
                <li className="flex items-center space-x-3">
                  <CreditCard className="w-5 h-5 text-purple-600" />
                  <span>Weekly Payouts + Multi-Currency</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Award className="w-5 h-5 text-purple-600" />
                  <span>Priority Marketplace Placement</span>
                </li>
                <li className="flex items-center space-x-3">
                  <HeadphonesIcon className="w-5 h-5 text-purple-600" />
                  <span>Dedicated Account Manager</span>
                </li>
              </ul>
              <Button 
                className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700" 
                onClick={() => handleUpgrade('pro-plus')}
                disabled={selectedPlan === 'pro-plus'}
              >
                {selectedPlan === 'pro-plus' ? 'Processing...' : 'Start Pro+ Plan'}
                <Crown className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Detailed Feature Comparison */}
        <Card className="mb-12">
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-center">
              Complete Feature Comparison
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-4 px-4 font-semibold">Feature</th>
                    <th className="text-center py-4 px-4 font-semibold">
                      <div className="flex items-center justify-center space-x-2">
                        <Star className="w-5 h-5 text-blue-600" />
                        <span>Pro</span>
                      </div>
                    </th>
                    <th className="text-center py-4 px-4 font-semibold">
                      <div className="flex items-center justify-center space-x-2">
                        <Crown className="w-5 h-5 text-purple-600" />
                        <span>Pro+</span>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((feature, index) => (
                    <tr key={index} className="border-b hover:bg-gray-50">
                      <td className="py-4 px-4 font-medium">{feature.name}</td>
                      <td className="py-4 px-4 text-center">
                        {renderFeatureValue(feature.pro)}
                      </td>
                      <td className="py-4 px-4 text-center">
                        {renderFeatureValue(feature.proPlus)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* FAQ Section */}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-center">
              Frequently Asked Questions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <h3 className="font-semibold mb-2">Can I change plans anytime?</h3>
                <p className="text-gray-600 mb-4">
                  Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately.
                </p>

                <h3 className="font-semibold mb-2">What payment methods do you accept?</h3>
                <p className="text-gray-600 mb-4">
                  We accept mobile money (MTN, Airtel), bank transfers, and major credit cards.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Is there a free trial?</h3>
                <p className="text-gray-600 mb-4">
                  Yes, all new MSMEs get a 14-day free trial of the Pro+ plan to experience all features.
                </p>

                <h3 className="font-semibold mb-2">What happens if I cancel?</h3>
                <p className="text-gray-600 mb-4">
                  You can cancel anytime. Your plan remains active until the end of your billing period.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MSMESubscriptionPlans;

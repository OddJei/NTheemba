import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { 
  Check, 
  X, 
  Star, 
  Zap,
  TrendingUp,
  Link2,
  DollarSign,
  BarChart3,
  HeadphonesIcon,
  Award,
  ArrowRight,
  Gift,
  Users,
  Crown
} from 'lucide-react';

interface PlanFeature {
  name: string;
  basic: boolean | string;
  pro: boolean | string;
}

const AffiliateSubscriptionPlans = () => {
  const [isYearly, setIsYearly] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<'basic' | 'pro' | null>(null);

  const pricing = {
    basic: {
      monthly: 0,
      yearly: 0,
    },
    pro: {
      monthly: 99,
      yearly: 990, // ~2 months free
    }
  };

  const features: PlanFeature[] = [
    {
      name: 'Campaign Access',
      basic: 'Public campaigns only',
      pro: 'Public + Pro-only campaigns + early access'
    },
    {
      name: 'Link Generation',
      basic: 'Single link + optional QR',
      pro: 'Branded short links + bulk generation'
    },
    {
      name: 'Campaign Presets',
      basic: false,
      pro: true
    },
    {
      name: 'Commission Rates',
      basic: 'Standard rates',
      pro: 'Higher rates on Pro campaigns'
    },
    {
      name: 'Tier-based Incentives',
      basic: false,
      pro: true
    },
    {
      name: 'Payout Frequency',
      basic: 'Monthly payouts',
      pro: 'Weekly payouts + priority processing'
    },
    {
      name: 'Minimum Threshold',
      basic: 'ZMW 100 minimum',
      pro: 'ZMW 50 minimum'
    },
    {
      name: 'Analytics & Tracking',
      basic: 'Basic CTR and conversions',
      pro: 'Advanced funnels + top-performing channels'
    },
    {
      name: 'Custom Reports',
      basic: false,
      pro: 'Custom report builder'
    },
    {
      name: 'Performance Insights',
      basic: 'Basic stats',
      pro: 'Detailed audience insights + optimization tips'
    },
    {
      name: 'Support Level',
      basic: 'Help center + chat/email',
      pro: 'Dedicated affiliate success manager'
    },
    {
      name: 'Training & Onboarding',
      basic: 'Self-service resources',
      pro: 'Priority onboarding + exclusive webinars'
    },
    {
      name: 'Referral Bonuses',
      basic: false,
      pro: 'Earn bonuses for referring new affiliates'
    },
    {
      name: 'API Access',
      basic: false,
      pro: 'Full API access for integrations'
    }
  ];

  const renderFeatureValue = (value: boolean | string) => {
    if (value === true) {
      return <Check className="w-5 h-5 text-green-600" />;
    }
    if (value === false) {
      return <X className="w-5 h-5 text-gray-400" />;
    }
    return <span className="text-sm text-gray-600 text-left">{value}</span>;
  };

  const handleUpgrade = (plan: 'basic' | 'pro') => {
    setSelectedPlan(plan);
    if (plan === 'basic') {
      // Redirect to basic signup flow
      console.log('Starting with Basic (Free) plan');
    } else {
      // Handle Pro plan payment
      console.log(`Upgrading to ${plan} plan (${isYearly ? 'yearly' : 'monthly'})`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Choose Your Affiliate Plan
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Start earning commissions and grow your affiliate income
          </p>
          
          {/* Billing Toggle */}
          <div className="flex items-center justify-center space-x-4">
            <span className={`font-medium ${!isYearly ? 'text-green-600' : 'text-gray-500'}`}>
              Monthly
            </span>
            <Switch 
              checked={isYearly} 
              onCheckedChange={setIsYearly}
            />
            <span className={`font-medium ${isYearly ? 'text-green-600' : 'text-gray-500'}`}>
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
          {/* Basic (Free) Plan */}
          <Card className="relative border-2 border-gray-200 hover:border-gray-300 transition-colors">
            <CardHeader className="text-center pb-8">
              <div className="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <Users className="w-8 h-8 text-gray-600" />
              </div>
              <CardTitle className="text-2xl font-bold">Basic Tier</CardTitle>
              <div className="text-4xl font-bold text-gray-600 mb-2">
                FREE
                <span className="text-lg text-gray-500 font-normal">
                  /forever
                </span>
              </div>
              <p className="text-gray-600">Perfect for getting started</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Access to public campaigns</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Basic link generation & QR codes</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Standard commission rates</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Monthly payouts (ZMW 100 min)</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Basic analytics & tracking</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span>Help center & email support</span>
                </li>
              </ul>
              <Button 
                variant="outline"
                className="w-full" 
                onClick={() => handleUpgrade('basic')}
                disabled={selectedPlan === 'basic'}
              >
                {selectedPlan === 'basic' ? 'Processing...' : 'Start Free'}
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>

          {/* Pro Plan */}
          <Card className="relative border-2 border-green-200 hover:border-green-300 transition-colors">
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <Badge className="bg-gradient-to-r from-green-600 to-emerald-600 text-white px-4 py-1">
                <Star className="w-4 h-4 mr-1" />
                MOST POPULAR
              </Badge>
            </div>
            <CardHeader className="text-center pb-8 pt-8">
              <div className="mx-auto w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center mb-4">
                <Star className="w-8 h-8 text-white" />
              </div>
              <CardTitle className="text-2xl font-bold">Pro Tier</CardTitle>
              <div className="text-4xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent mb-2">
                ZMW {isYearly ? pricing.pro.yearly : pricing.pro.monthly}
                <span className="text-lg text-gray-500 font-normal">
                  /{isYearly ? 'year' : 'month'}
                </span>
              </div>
              <p className="text-gray-600">For serious affiliates</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="font-medium">Everything in Basic, plus:</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Zap className="w-5 h-5 text-green-600" />
                  <span>Pro-only campaigns + early access</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Link2 className="w-5 h-5 text-green-600" />
                  <span>Branded links + bulk generation</span>
                </li>
                <li className="flex items-center space-x-3">
                  <DollarSign className="w-5 h-5 text-green-600" />
                  <span>Higher commission rates</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Award className="w-5 h-5 text-green-600" />
                  <span>Weekly payouts (ZMW 50 min)</span>
                </li>
                <li className="flex items-center space-x-3">
                  <BarChart3 className="w-5 h-5 text-green-600" />
                  <span>Advanced analytics & custom reports</span>
                </li>
                <li className="flex items-center space-x-3">
                  <HeadphonesIcon className="w-5 h-5 text-green-600" />
                  <span>Dedicated success manager</span>
                </li>
                <li className="flex items-center space-x-3">
                  <Gift className="w-5 h-5 text-green-600" />
                  <span>Referral bonuses + API access</span>
                </li>
              </ul>
              <Button 
                className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700" 
                onClick={() => handleUpgrade('pro')}
                disabled={selectedPlan === 'pro'}
              >
                {selectedPlan === 'pro' ? 'Processing...' : 'Upgrade to Pro'}
                <Star className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Commission Comparison */}
        <Card className="mb-12">
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-center">
              Commission Rate Comparison
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-8 text-center">
              <div className="p-6 bg-gray-50 rounded-lg">
                <h3 className="font-bold text-lg mb-2">Standard Campaigns</h3>
                <div className="text-3xl font-bold text-gray-600 mb-2">5-8%</div>
                <p className="text-sm text-gray-600">Available in Basic & Pro</p>
              </div>
              <div className="p-6 bg-green-50 rounded-lg border-2 border-green-200">
                <h3 className="font-bold text-lg mb-2">Pro-Only Campaigns</h3>
                <div className="text-3xl font-bold text-green-600 mb-2">10-15%</div>
                <p className="text-sm text-green-600">Exclusive to Pro members</p>
              </div>
              <div className="p-6 bg-blue-50 rounded-lg">
                <h3 className="font-bold text-lg mb-2">Tier Bonuses</h3>
                <div className="text-3xl font-bold text-blue-600 mb-2">+2%</div>
                <p className="text-sm text-blue-600">Pro tier performance bonus</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Feature Comparison Table */}
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
                        <Users className="w-5 h-5 text-gray-600" />
                        <span>Basic</span>
                      </div>
                    </th>
                    <th className="text-center py-4 px-4 font-semibold">
                      <div className="flex items-center justify-center space-x-2">
                        <Star className="w-5 h-5 text-green-600" />
                        <span>Pro</span>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((feature, index) => (
                    <tr key={index} className="border-b hover:bg-gray-50">
                      <td className="py-4 px-4 font-medium">{feature.name}</td>
                      <td className="py-4 px-4 text-center">
                        {renderFeatureValue(feature.basic)}
                      </td>
                      <td className="py-4 px-4 text-center">
                        {renderFeatureValue(feature.pro)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Success Stories */}
        <Card className="mb-12">
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-center">
              Affiliate Success Stories
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-8">
              <div className="text-center p-6">
                <div className="w-16 h-16 bg-green-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                  <Crown className="w-8 h-8 text-green-600" />
                </div>
                <h3 className="font-bold mb-2">Sarah M.</h3>
                <p className="text-gray-600 mb-4">Pro Affiliate</p>
                <p className="text-sm text-gray-600">
                  "Upgraded to Pro and doubled my earnings in 3 months with exclusive campaigns!"
                </p>
                <div className="text-2xl font-bold text-green-600 mt-4">ZMW 2,500/month</div>
              </div>
              
              <div className="text-center p-6">
                <div className="w-16 h-16 bg-blue-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                  <TrendingUp className="w-8 h-8 text-blue-600" />
                </div>
                <h3 className="font-bold mb-2">James K.</h3>
                <p className="text-gray-600 mb-4">Pro Affiliate</p>
                <p className="text-sm text-gray-600">
                  "The advanced analytics helped me optimize my strategy and increase conversions by 40%."
                </p>
                <div className="text-2xl font-bold text-blue-600 mt-4">ZMW 1,800/month</div>
              </div>
              
              <div className="text-center p-6">
                <div className="w-16 h-16 bg-purple-100 rounded-full mx-auto mb-4 flex items-center justify-center">
                  <Award className="w-8 h-8 text-purple-600" />
                </div>
                <h3 className="font-bold mb-2">Maria L.</h3>
                <p className="text-gray-600 mb-4">Pro Affiliate</p>
                <p className="text-sm text-gray-600">
                  "Weekly payouts and dedicated support made all the difference in scaling my business."
                </p>
                <div className="text-2xl font-bold text-purple-600 mt-4">ZMW 3,200/month</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* FAQ */}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-center">
              Frequently Asked Questions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <h3 className="font-semibold mb-2">Can I start with Basic and upgrade later?</h3>
                <p className="text-gray-600 mb-4">
                  Absolutely! You can upgrade to Pro at any time and start accessing exclusive campaigns immediately.
                </p>

                <h3 className="font-semibold mb-2">How are commissions calculated?</h3>
                <p className="text-gray-600 mb-4">
                  Commissions are based on successful conversions. Pro members get higher rates and access to premium campaigns.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">When do I get paid?</h3>
                <p className="text-gray-600 mb-4">
                  Basic: Monthly payouts with ZMW 100 minimum. Pro: Weekly payouts with ZMW 50 minimum.
                </p>

                <h3 className="font-semibold mb-2">What if I want to cancel Pro?</h3>
                <p className="text-gray-600 mb-4">
                  You can downgrade to Basic anytime. Your Pro benefits remain active until the end of your billing period.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AffiliateSubscriptionPlans;

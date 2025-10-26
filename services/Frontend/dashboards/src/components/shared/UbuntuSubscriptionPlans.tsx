import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { 
  Heart, 
  Crown, 
  Zap, 
  Check, 
  Star,
  Users,
  Handshake,
  Globe,
  Target,
  TrendingUp,
  Gift,
  Shield,
  Headphones,
  ArrowRight
} from "lucide-react";

const UbuntuSubscriptionPlans = () => {
  const [isYearly, setIsYearly] = useState(false);

  const plans = [
    {
      id: 'ubuntu-community',
      name: 'Ubuntu Community',
      subtitle: 'Free Forever',
      price: { monthly: 0, yearly: 0 },
      color: 'from-orange-500 to-red-500',
      icon: <Heart className="w-6 h-6" />,
      popular: false,
      description: 'Join the African entrepreneurship community with Ubuntu spirit',
      features: [
        'Ubuntu Community Access',
        'Basic Cross-Promotion',
        'Community Support',
        'Ubuntu Points System',
        'Monthly Community Events',
        'Basic Analytics',
        'Standard Commission Rates'
      ],
      limitations: [
        'Limited to 5 cross-promotions per month',
        'Basic reporting only',
        'Community support only'
      ]
    },
    {
      id: 'ubuntu-pro',
      name: 'Ubuntu Pro',
      subtitle: 'Most Popular',
      price: { monthly: 99, yearly: 990 },
      color: 'from-blue-500 to-purple-500',
      icon: <Crown className="w-6 h-6" />,
      popular: true,
      description: 'Enhanced Ubuntu experience with professional tools',
      features: [
        'Everything in Community',
        'Unlimited Cross-Promotions',
        'Priority in Community Feed',
        'Advanced Ubuntu Analytics',
        'Weekly 1-on-1 Mentorship',
        'Pro Commission Rates (+2%)',
        'Custom Ubuntu Badge',
        'Early Access to Features',
        'Priority Customer Support'
      ],
      limitations: []
    },
    {
      id: 'ubuntu-champion',
      name: 'Ubuntu Champion',
      subtitle: 'For Ubuntu Leaders',
      price: { monthly: 299, yearly: 2990 },
      color: 'from-yellow-500 to-orange-500',
      icon: <Star className="w-6 h-6" />,
      popular: false,
      description: 'Lead the Ubuntu movement with premium features',
      features: [
        'Everything in Pro',
        'Ubuntu Leader Badge',
        'Host Community Events',
        'Mentor Other Members',
        'Champion Commission Rates (+5%)',
        'Dedicated Account Manager',
        'Custom Branding Options',
        'API Access for Integration',
        'White-label Solutions',
        'Quarterly Ubuntu Summit Access'
      ],
      limitations: []
    }
  ];

  const getPrice = (plan: typeof plans[0]) => {
    const price = isYearly ? plan.price.yearly : plan.price.monthly;
    const period = isYearly ? 'year' : 'month';
    return { price, period };
  };

  const getSavings = (plan: typeof plans[0]) => {
    if (plan.price.yearly === 0) return null;
    const monthlyCost = plan.price.monthly * 12;
    const savings = monthlyCost - plan.price.yearly;
    const percentage = Math.round((savings / monthlyCost) * 100);
    return { amount: savings, percentage };
  };

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-3 sm:space-y-4">
        <div className="flex items-center justify-center space-x-2 sm:space-x-3">
          <Heart className="w-6 h-6 sm:w-8 sm:h-8 text-orange-600" />
          <h1 className="text-2xl sm:text-3xl font-bold">Ubuntu Subscription Plans</h1>
          <Heart className="w-6 h-6 sm:w-8 sm:h-8 text-red-600" />
        </div>
        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto px-4">
          Choose your Ubuntu journey. From community membership to champion leadership - 
          find the plan that matches your commitment to African entrepreneurship.
        </p>
        
        {/* Billing Toggle */}
        <div className="flex items-center justify-center space-x-2 sm:space-x-4 bg-muted p-2 rounded-lg w-fit mx-auto">
          <span className={`text-xs sm:text-sm ${!isYearly ? 'font-semibold' : 'text-muted-foreground'}`}>Monthly</span>
          <Switch checked={isYearly} onCheckedChange={setIsYearly} />
          <span className={`text-xs sm:text-sm ${isYearly ? 'font-semibold' : 'text-muted-foreground'}`}>Yearly</span>
          <Badge className="bg-green-100 text-green-800 ml-2 text-xs">Save up to 17%</Badge>
        </div>
      </div>

      {/* Subscription Plans */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
        {plans.map((plan) => {
          const { price, period } = getPrice(plan);
          const savings = getSavings(plan);
          
          return (
            <Card key={plan.id} className={`relative ${plan.popular ? 'ring-2 ring-blue-500 transform scale-[1.02] sm:scale-105' : ''} hover:shadow-md transition-all`}>
              {plan.popular && (
                <div className="absolute -top-2 sm:-top-3 left-1/2 transform -translate-x-1/2">
                  <Badge className="bg-blue-500 text-white px-2 py-1 sm:px-4 sm:py-1 text-xs">Most Popular</Badge>
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
                
                {plan.limitations.length > 0 && (
                  <div className="border-t pt-3 sm:pt-4">
                    <p className="text-xs sm:text-sm text-muted-foreground font-medium mb-2">Limitations:</p>
                    <div className="space-y-1">
                      {plan.limitations.map((limitation, index) => (
                        <p key={index} className="text-xs text-muted-foreground">• {limitation}</p>
                      ))}
                    </div>
                  </div>
                )}
                
                <Button 
                  className={`w-full py-2 sm:py-3 text-sm sm:text-base ${plan.popular ? `bg-gradient-to-r ${plan.color} hover:opacity-90` : ''}`}
                  variant={plan.popular ? "default" : "outline"}
                >
                  {plan.id === 'ubuntu-community' ? 'Join Community' : 'Upgrade Now'}
                  <ArrowRight className="w-3 h-3 sm:w-4 sm:h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Feature Comparison */}
      <Tabs defaultValue="features" className="mt-6 sm:mt-8">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="features" className="text-sm sm:text-base">Feature Comparison</TabsTrigger>
          <TabsTrigger value="ubuntu-benefits" className="text-sm sm:text-base">Ubuntu Benefits</TabsTrigger>
        </TabsList>
        
        <TabsContent value="features" className="mt-4 sm:mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg sm:text-xl">Detailed Feature Comparison</CardTitle>
              <CardDescription className="text-sm">
                Compare all features across Ubuntu subscription tiers
              </CardDescription>
            </CardHeader>
            <CardContent className="p-3 sm:p-6">
              <div className="overflow-x-auto">
                <table className="w-full text-xs sm:text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-1 sm:p-2">Feature</th>
                      <th className="text-center p-1 sm:p-2">Community</th>
                      <th className="text-center p-1 sm:p-2">Pro</th>
                      <th className="text-center p-1 sm:p-2">Champion</th>
                    </tr>
                  </thead>
                  <tbody className="space-y-2">
                    {[
                      { feature: 'Ubuntu Community Access', community: true, pro: true, champion: true },
                      { feature: 'Cross-Promotions per Month', community: '5', pro: 'Unlimited', champion: 'Unlimited' },
                      { feature: 'Commission Rate Bonus', community: '0%', pro: '+2%', champion: '+5%' },
                      { feature: 'Analytics & Reporting', community: 'Basic', pro: 'Advanced', champion: 'Premium + API' },
                      { feature: 'Community Support', community: true, pro: true, champion: true },
                      { feature: 'Priority Support', community: false, pro: true, champion: true },
                      { feature: 'Dedicated Account Manager', community: false, pro: false, champion: true },
                      { feature: 'Custom Ubuntu Badge', community: false, pro: true, champion: true },
                      { feature: 'Host Community Events', community: false, pro: false, champion: true },
                      { feature: 'Mentor Other Members', community: false, pro: false, champion: true },
                      { feature: 'White-label Solutions', community: false, pro: false, champion: true }
                    ].map((row, index) => (
                      <tr key={index} className="border-b">
                        <td className="p-2 font-medium">{row.feature}</td>
                        <td className="p-2 text-center">
                          {typeof row.community === 'boolean' ? 
                            (row.community ? <Check className="w-4 h-4 text-green-500 mx-auto" /> : '—') : 
                            row.community
                          }
                        </td>
                        <td className="p-2 text-center">
                          {typeof row.pro === 'boolean' ? 
                            (row.pro ? <Check className="w-4 h-4 text-green-500 mx-auto" /> : '—') : 
                            row.pro
                          }
                        </td>
                        <td className="p-2 text-center">
                          {typeof row.champion === 'boolean' ? 
                            (row.champion ? <Check className="w-4 h-4 text-green-500 mx-auto" /> : '—') : 
                            row.champion
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="ubuntu-benefits" className="mt-4 sm:mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            <Card className="bg-gradient-to-br from-orange-50 to-red-50 border-orange-200">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
                  <Heart className="w-4 h-4 sm:w-5 sm:h-5 text-orange-600" />
                  <span>Ubuntu Philosophy Benefits</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 sm:space-y-4">
                <div className="flex items-start space-x-3">
                  <Users className="w-4 h-4 sm:w-5 sm:h-5 text-orange-500 mt-1 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-sm sm:text-base">Community Connection</h4>
                    <p className="text-xs sm:text-sm text-muted-foreground">Connect with like-minded African entrepreneurs who share your values.</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <Handshake className="w-4 h-4 sm:w-5 sm:h-5 text-red-500 mt-1 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-sm sm:text-base">Mutual Support</h4>
                    <p className="text-xs sm:text-sm text-muted-foreground">Give and receive support in true Ubuntu spirit - we grow together.</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <Globe className="w-4 h-4 sm:w-5 sm:h-5 text-yellow-500 mt-1 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-sm sm:text-base">African Unity</h4>
                    <p className="text-sm text-muted-foreground">Be part of a movement strengthening African business networks.</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-blue-50 to-purple-50 border-blue-200">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
                  <TrendingUp className="w-4 h-4 sm:w-5 sm:h-5 text-blue-600" />
                  <span>Business Growth Benefits</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 sm:space-y-4">
                <div className="flex items-start space-x-3">
                  <Target className="w-4 h-4 sm:w-5 sm:h-5 text-blue-500 mt-1 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-sm sm:text-base">Increased Visibility</h4>
                    <p className="text-xs sm:text-sm text-muted-foreground">Get your business promoted by community members across Africa.</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <Gift className="w-4 h-4 sm:w-5 sm:h-5 text-purple-500 mt-1 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-sm sm:text-base">Higher Earnings</h4>
                    <p className="text-xs sm:text-sm text-muted-foreground">Earn bonus commissions through Ubuntu cross-promotion activities.</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <Shield className="w-4 h-4 sm:w-5 sm:h-5 text-green-500 mt-1 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-sm sm:text-base">Trusted Network</h4>
                    <p className="text-xs sm:text-sm text-muted-foreground">Build relationships with verified, trustworthy business partners.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Call to Action */}
      <Card className="bg-gradient-to-r from-orange-600 to-red-600 text-white">
        <CardContent className="p-4 sm:p-6 lg:p-8 text-center">
          <h3 className="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Ready to Embrace Ubuntu?</h3>
          <p className="text-orange-100 mb-4 sm:mb-6 max-w-2xl mx-auto text-sm sm:text-base px-2">
            Join thousands of African entrepreneurs who are building success together. 
            Start with our free community and upgrade as you grow.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
            <Button size="lg" className="bg-white text-orange-600 hover:bg-orange-50 text-sm sm:text-base py-2 sm:py-3">
              <Heart className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
              Start with Free Community
            </Button>
            <Button size="lg" variant="outline" className="border-white text-white hover:bg-white hover:text-orange-600 text-sm sm:text-base py-2 sm:py-3">
              <Headphones className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
              Talk to Ubuntu Advisor
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default UbuntuSubscriptionPlans;

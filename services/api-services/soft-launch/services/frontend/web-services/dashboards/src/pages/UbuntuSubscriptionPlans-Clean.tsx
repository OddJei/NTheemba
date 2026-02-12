import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Heart,
  Users,
  Building,
  TrendingUp,
  Check,
  Crown,
  Star,
  Gift,
  Zap,
  Shield,
  Clock
} from 'lucide-react';

const UbuntuSubscriptionPlans = () => {
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

  const handleUpgrade = (planType: string) => {
    setSelectedPlan(planType);
    // In real app, this would trigger payment flow or API call
    console.log(`Upgrading to ${planType} plan`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-red-50 to-yellow-50 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Ubuntu Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 rounded-full mb-4">
            <Heart className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent">
            Ubuntu Subscription Plans
          </h1>
          <p className="text-lg text-gray-600 max-w-3xl mx-auto mb-6">
            "I am because we are" - Choose the plan that supports your Ubuntu journey and African business growth
          </p>
          
          {/* Free Community Notice */}
          <div className="bg-gradient-to-r from-green-100 to-blue-100 border border-green-200 rounded-lg p-4 max-w-2xl mx-auto">
            <div className="flex items-center justify-center space-x-2 mb-2">
              <Heart className="w-5 h-5 text-green-600" />
              <span className="font-semibold text-green-800">Ubuntu Community is Forever Free</span>
            </div>
            <p className="text-sm text-green-700">
              Join our community of African entrepreneurs with no subscription required. 
              Business tools are paid to fund platform development.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Free Ubuntu Community */}
          <Card className="relative border-2 border-green-300 shadow-lg">
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <Badge className="bg-green-600 text-white px-4 py-1 text-sm">
                Forever Free
              </Badge>
            </div>
            <CardHeader className="text-center pb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Users className="w-8 h-8 text-white" />
              </div>
              <CardTitle className="text-2xl font-bold text-green-800">Ubuntu Community</CardTitle>
              <div className="text-4xl font-bold text-green-600 mt-2">
                ZMW 0<span className="text-lg font-normal text-gray-500">/forever</span>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Community access with Ubuntu philosophy
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Ubuntu Community Access</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Peer-to-Peer Networking</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Business Opportunity Sharing</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Community Support System</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Ubuntu Philosophy Integration</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Mentorship Circles</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-sm">Community Recognition</span>
                </div>
              </div>

              <div className="pt-4 border-t">
                <p className="text-xs text-gray-500 mb-4 text-center">
                  No subscription required - Join today
                </p>
                <Button 
                  className="w-full bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700"
                  onClick={() => handleUpgrade('community')}
                >
                  <Heart className="w-4 h-4 mr-2" />
                  Join Ubuntu Community
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* MSME Business Tools */}
          <Card className="relative border-2 border-blue-300 shadow-lg">
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <Badge className="bg-blue-600 text-white px-4 py-1 text-sm">
                Business Tools
              </Badge>
            </div>
            <CardHeader className="text-center pb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Building className="w-8 h-8 text-white" />
              </div>
              <CardTitle className="text-2xl font-bold text-blue-800">MSME Pro</CardTitle>
              <div className="text-4xl font-bold text-blue-600 mt-2">
                ZMW 399<span className="text-lg font-normal text-gray-500">/month</span>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Advanced business management tools
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
                <p className="text-xs text-green-700 font-medium text-center">
                  ✨ Includes FREE Ubuntu Community Access
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Advanced Business Analytics</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Customer Relationship Management</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Marketing Automation Suite</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Workflow Automation</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Third-Party Integrations</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Priority Customer Support</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-blue-600" />
                  <span className="text-sm">Custom Business Reports</span>
                </div>
              </div>

              <div className="pt-4 border-t">
                <p className="text-xs text-gray-500 mb-4 text-center">
                  7-day free trial • Cancel anytime
                </p>
                <Button 
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                  onClick={() => handleUpgrade('msme-pro')}
                >
                  <Building className="w-4 h-4 mr-2" />
                  Start MSME Pro
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Affiliate Business Tools */}
          <Card className="relative border-2 border-purple-300 shadow-lg">
            <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
              <Badge className="bg-purple-600 text-white px-4 py-1 text-sm">
                Affiliate Tools
              </Badge>
            </div>
            <CardHeader className="text-center pb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <TrendingUp className="w-8 h-8 text-white" />
              </div>
              <CardTitle className="text-2xl font-bold text-purple-800">Affiliate Pro</CardTitle>
              <div className="text-4xl font-bold text-purple-600 mt-2">
                ZMW 199<span className="text-lg font-normal text-gray-500">/month</span>
              </div>
              <p className="text-sm text-gray-600 mt-2">
                Professional affiliate marketing platform
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
                <p className="text-xs text-green-700 font-medium text-center">
                  ✨ Includes FREE Ubuntu Community Access
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Advanced Affiliate Management</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Multi-Tier Commission Tracking</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Performance Analytics</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Automated Payouts</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Campaign Management</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Link & Banner Generator</span>
                </div>
                <div className="flex items-center space-x-3">
                  <Check className="w-5 h-5 text-purple-600" />
                  <span className="text-sm">Real-time Reporting</span>
                </div>
              </div>

              <div className="pt-4 border-t">
                <p className="text-xs text-gray-500 mb-4 text-center">
                  7-day free trial • Cancel anytime
                </p>
                <Button 
                  className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                  onClick={() => handleUpgrade('affiliate-pro')}
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Start Affiliate Pro
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Ubuntu Philosophy Section */}
        <Card className="mb-8 border-2 border-orange-200 bg-gradient-to-r from-orange-50 to-red-50">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-orange-800 flex items-center justify-center">
              <Heart className="w-6 h-6 mr-2" />
              Ubuntu Philosophy in Action
            </CardTitle>
            <p className="text-orange-700 mt-2">
              "I am because we are" - Our community-first approach to business growth
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center p-4">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Users className="w-6 h-6 text-green-600" />
                </div>
                <h3 className="font-semibold text-green-800 mb-2">Free Community</h3>
                <p className="text-sm text-gray-600">
                  Ubuntu community access is forever free. Connect, share, and grow together with fellow African entrepreneurs.
                </p>
              </div>
              <div className="text-center p-4">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Building className="w-6 h-6 text-blue-600" />
                </div>
                <h3 className="font-semibold text-blue-800 mb-2">Business Tools</h3>
                <p className="text-sm text-gray-600">
                  Advanced business and affiliate tools require subscriptions to fund platform development and support.
                </p>
              </div>
              <div className="text-center p-4">
                <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Heart className="w-6 h-6 text-orange-600" />
                </div>
                <h3 className="font-semibold text-orange-800 mb-2">Unified Growth</h3>
                <p className="text-sm text-gray-600">
                  MSMEs can also be affiliates, promoting each other's businesses and creating a unified African ecosystem.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Call to Action */}
        <Card className="border-2 border-orange-300 bg-gradient-to-r from-orange-100 to-red-100">
          <CardContent className="text-center p-8">
            <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 rounded-full flex items-center justify-center mx-auto mb-6">
              <Heart className="w-10 h-10 text-white" />
            </div>
            <h2 className="text-3xl font-bold mb-4 bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent">
              Start Your Ubuntu Journey Today
            </h2>
            <p className="text-lg text-gray-600 mb-6 max-w-2xl mx-auto">
              Join thousands of African entrepreneurs building businesses together. 
              Start with our free community and upgrade to unlock powerful business tools when you're ready.
            </p>
            <Button 
              size="lg" 
              className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700"
              onClick={() => handleUpgrade('community')}
            >
              <Heart className="w-5 h-5 mr-2" />
              Begin Your Ubuntu Journey
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default UbuntuSubscriptionPlans;

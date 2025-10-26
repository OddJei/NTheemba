import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SubscriptionPlans from '@/components/shared/SubscriptionPlans';
import SubscriptionManagement from '@/components/shared/SubscriptionManagement';
import EarningsTracker from '@/components/shared/EarningsTracker';
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

const SubscriptionDemo = () => {
  const [userType, setUserType] = useState<'msme' | 'affiliate'>('affiliate');
  const [currentPlan, setCurrentPlan] = useState('basic');
  const [viewMode, setViewMode] = useState<'plans' | 'management' | 'tracker'>('plans');

  const handlePlanSelect = (planId: string, billing: 'monthly' | 'yearly') => {
    console.log('Plan selected:', planId, billing);
    setCurrentPlan(planId);
    setViewMode('management');
  };

  // Mock data for earnings tracker
  const earningsData = {
    msme: {
      basic: { monthlyEarnings: 0, subscriptionCost: 0, salesCount: 0, commissionRate: 1.00 },
      pro: { monthlyEarnings: 67.50, subscriptionCost: 50, salesCount: 45, commissionRate: 1.50 },
      elite: { monthlyEarnings: 180.00, subscriptionCost: 150, salesCount: 90, commissionRate: 2.00 }
    },
    affiliate: {
      basic: { monthlyEarnings: 45.00, subscriptionCost: 0, salesCount: 45, commissionRate: 1.00 },
      pro: { monthlyEarnings: 67.50, subscriptionCost: 50, salesCount: 45, commissionRate: 1.50 }
    }
  };

  const currentEarnings = userType === 'msme' 
    ? earningsData.msme[currentPlan as keyof typeof earningsData.msme] || earningsData.msme.basic
    : earningsData.affiliate[currentPlan as keyof typeof earningsData.affiliate] || earningsData.affiliate.basic;

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Subscription System Demo</h1>
            <p className="text-muted-foreground text-sm sm:text-base">
            Test the complete subscription flow for NTheemba
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Label htmlFor="user-type">User Type:</Label>
          <div className="flex items-center space-x-2">
            <span className={userType === 'affiliate' ? 'font-semibold' : 'text-muted-foreground'}>Affiliate</span>
            <Switch 
              id="user-type"
              checked={userType === 'msme'} 
              onCheckedChange={(checked) => setUserType(checked ? 'msme' : 'affiliate')}
            />
            <span className={userType === 'msme' ? 'font-semibold' : 'text-muted-foreground'}>MSME</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-2">
            <Button 
              variant={viewMode === 'plans' ? 'default' : 'outline'} 
              onClick={() => setViewMode('plans')}
              size="sm"
            >
              View Plans
            </Button>
            <Button 
              variant={viewMode === 'management' ? 'default' : 'outline'} 
              onClick={() => setViewMode('management')}
              size="sm"
            >
              Manage Subscription
            </Button>
            <Button 
              variant={viewMode === 'tracker' ? 'default' : 'outline'} 
              onClick={() => setViewMode('tracker')}
              size="sm"
            >
              Earnings Tracker
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Current Plan: <span className="font-semibold">{currentPlan}</span> | 
            User Type: <span className="font-semibold">{userType}</span>
          </p>
        </CardContent>
      </Card>

      {/* Content */}
      {viewMode === 'plans' && (
        <SubscriptionPlans 
          userType={userType}
          currentPlan={currentPlan}
          onPlanSelect={handlePlanSelect}
        />
      )}

      {viewMode === 'management' && (
        <SubscriptionManagement userType={userType} />
      )}

      {viewMode === 'tracker' && (
        <EarningsTracker
          userType={userType}
          currentPlan={currentPlan}
          monthlyEarnings={currentEarnings.monthlyEarnings}
          subscriptionCost={currentEarnings.subscriptionCost}
          salesCount={currentEarnings.salesCount}
          commissionRate={currentEarnings.commissionRate}
        />
      )}

      {/* Info Panel */}
      <Card className="bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-lg">Demo Information</CardTitle>
          <CardDescription>
            This is a demo of the complete subscription system for NTheemba
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>
            <h4 className="font-semibold">Features Demonstrated:</h4>
            <ul className="list-disc list-inside space-y-1 mt-2 text-xs">
              <li>Complete subscription plan selection for both MSME and Affiliate users</li>
              <li>Mobile money payment integration (simulated)</li>
              <li>Subscription management dashboard with billing info and earnings</li>
              <li>Break-even calculations and ROI tracking</li>
              <li>Responsive design for all screen sizes</li>
              <li>Plan comparison and upgrade recommendations</li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold">Test Scenarios:</h4>
            <ul className="list-disc list-inside space-y-1 mt-2 text-xs">
              <li>Switch between MSME and Affiliate user types</li>
              <li>Try selecting different plans (Basic/Pro/Elite)</li>
              <li>Test the payment flow (uses mock data)</li>
              <li>View earnings tracker with different subscription costs</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SubscriptionDemo;

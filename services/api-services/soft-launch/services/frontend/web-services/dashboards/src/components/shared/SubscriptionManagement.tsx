import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import SubscriptionPlans from "@/components/shared/SubscriptionPlans";
import { 
  Crown, 
  CreditCard, 
  Calendar, 
  TrendingUp, 
  AlertTriangle,
  CheckCircle,
  Gift,
  Star,
  Users,
  ArrowRight
} from "lucide-react";

interface SubscriptionManagementProps {
  userType: 'msme' | 'affiliate';
}

const SubscriptionManagement: React.FC<SubscriptionManagementProps> = ({ userType }) => {
  const [currentPlan, setCurrentPlan] = useState('basic'); // This would come from API
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [showPlans, setShowPlans] = useState(false);

  // Mock subscription data - this would come from your API
  const subscriptionData = {
    plan: currentPlan,
    billingCycle: billingCycle,
    nextBilling: '2025-10-05',
    status: 'active',
    daysUntilBilling: 30,
    currentPeriodSales: 45, // for break-even calculation
    breakEvenTarget: userType === 'msme' ? 50 : 34, // based on plan
    totalEarnings: 2340.50,
    pendingPayouts: 125.00
  };

  const planDetails = {
    basic: { name: 'Basic', price: 0, commission: 1.00, color: 'text-blue-600' },
    pro: { name: 'Pro', price: userType === 'msme' ? 50 : 50, commission: userType === 'msme' ? 1.50 : 1.50, color: 'text-purple-600' },
    elite: { name: 'Elite', price: 150, commission: 2.00, color: 'text-yellow-600' }
  };

  const currentPlanDetails = planDetails[currentPlan as keyof typeof planDetails];

  const handlePlanSelect = (planId: string, billing: 'monthly' | 'yearly') => {
    console.log('Plan selected:', planId, billing);
    // Handle plan selection logic here
    setCurrentPlan(planId);
    setBillingCycle(billing);
    setShowPlans(false);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" />Active</Badge>;
      case 'trial':
        return <Badge className="bg-blue-100 text-blue-800"><Gift className="w-3 h-3 mr-1" />Free Trial</Badge>;
      case 'cancelled':
        return <Badge className="bg-red-100 text-red-800"><AlertTriangle className="w-3 h-3 mr-1" />Cancelled</Badge>;
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
  };

  if (showPlans) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl sm:text-2xl font-bold">Choose Your Plan</h2>
          <Button variant="outline" onClick={() => setShowPlans(false)}>
            Back to Dashboard
          </Button>
        </div>
        <SubscriptionPlans 
          userType={userType}
          currentPlan={currentPlan}
          onPlanSelect={handlePlanSelect}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Subscription Management</h1>
          <p className="text-muted-foreground text-sm sm:text-base">Manage your plan and billing settings</p>
        </div>
        <Button onClick={() => setShowPlans(true)} className="w-full sm:w-auto">
          View All Plans
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>

      {/* Current Plan Overview */}
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader>
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
            <div>
              <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
                {currentPlan === 'elite' ? <Crown className="w-5 h-5 text-yellow-600" /> :
                 currentPlan === 'pro' ? <Star className="w-5 h-5 text-purple-600" /> :
                 <Users className="w-5 h-5 text-blue-600" />}
                <span className={currentPlanDetails.color}>{currentPlanDetails.name} Plan</span>
              </CardTitle>
              <CardDescription className="text-sm">
                Your current subscription tier
              </CardDescription>
            </div>
            {getStatusBadge(subscriptionData.status)}
          </div>
        </CardHeader>
        <CardContent className="space-y-4 sm:space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-xs sm:text-sm text-muted-foreground">Monthly Cost</p>
              <p className="text-xl sm:text-2xl font-bold">
                {currentPlanDetails.price === 0 ? 'Free' : `ZMW ${currentPlanDetails.price}`}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs sm:text-sm text-muted-foreground">Commission Rate</p>
              <p className="text-xl sm:text-2xl font-bold text-green-600">
                ZMW {currentPlanDetails.commission.toFixed(2)}
              </p>
              <p className="text-xs text-muted-foreground">per sale</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs sm:text-sm text-muted-foreground">Next Billing</p>
              <p className="text-sm sm:text-base font-semibold">
                {new Date(subscriptionData.nextBilling).toLocaleDateString()}
              </p>
              <p className="text-xs text-muted-foreground">
                {subscriptionData.daysUntilBilling} days away
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs sm:text-sm text-muted-foreground">Total Earnings</p>
              <p className="text-xl sm:text-2xl font-bold text-green-600">
                ZMW {subscriptionData.totalEarnings.toLocaleString()}
              </p>
            </div>
          </div>

          {/* Break-even Progress (for paid plans) */}
          {currentPlanDetails.price > 0 && (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="font-semibold text-sm sm:text-base">Break-even Progress</h4>
                <span className="text-xs sm:text-sm text-muted-foreground">
                  {subscriptionData.currentPeriodSales}/{subscriptionData.breakEvenTarget} sales
                </span>
              </div>
              <Progress 
                value={(subscriptionData.currentPeriodSales / subscriptionData.breakEvenTarget) * 100} 
                className="h-2"
              />
              <p className="text-xs sm:text-sm text-muted-foreground">
                {subscriptionData.currentPeriodSales >= subscriptionData.breakEvenTarget 
                  ? '🎉 You\'ve reached your break-even point this month!'
                  : `${subscriptionData.breakEvenTarget - subscriptionData.currentPeriodSales} more sales needed to break even this month`
                }
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Billing Information */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
              <CreditCard className="w-5 h-5 text-blue-600" />
              <span>Billing Information</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Plan</span>
                <span className="font-semibold">{currentPlanDetails.name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Billing Cycle</span>
                <span className="font-semibold capitalize">{billingCycle}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Next Payment</span>
                <span className="font-semibold">
                  {currentPlanDetails.price === 0 ? 'N/A' : `ZMW ${currentPlanDetails.price}`}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Payment Method</span>
                <span className="font-semibold">MTN Mobile Money</span>
              </div>
            </div>
            <div className="pt-4 border-t">
              <Button variant="outline" className="w-full text-sm">
                Update Payment Method
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <span>Earnings Overview</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">This Month</span>
                <span className="font-bold text-green-600">
                  ZMW {(subscriptionData.currentPeriodSales * currentPlanDetails.commission).toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Pending Payouts</span>
                <span className="font-bold text-orange-600">
                  ZMW {subscriptionData.pendingPayouts.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Total Lifetime</span>
                <span className="font-bold text-blue-600">
                  ZMW {subscriptionData.totalEarnings.toFixed(2)}
                </span>
              </div>
            </div>
            <div className="pt-4 border-t">
              <Button variant="outline" className="w-full text-sm">
                View Detailed Reports
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Upgrade Recommendations */}
      {currentPlan === 'basic' && (
        <Alert>
          <Gift className="h-4 w-4" />
          <AlertDescription className="text-sm">
            <strong>Ready to earn more?</strong> Upgrade to Pro and increase your commission rate to ZMW {planDetails.pro.commission}/sale. 
            With your current performance, you could earn an extra ZMW {((planDetails.pro.commission - planDetails.basic.commission) * subscriptionData.currentPeriodSales).toFixed(2)} this month!
          </AlertDescription>
        </Alert>
      )}

      {currentPlan === 'pro' && userType === 'msme' && (
        <Alert>
          <Crown className="h-4 w-4" />
          <AlertDescription className="text-sm">
            <strong>Elite tier available!</strong> High-volume MSMEs can access our Elite tier with ZMW {planDetails.elite.commission}/sale commission rate. 
            Contact our team to see if you qualify for an invite.
          </AlertDescription>
        </Alert>
      )}

      {/* Plan Comparison Quick View */}
      <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-lg sm:text-xl">Plan Comparison</CardTitle>
          <CardDescription className="text-sm">
            See how different plans can impact your earnings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Object.entries(planDetails).map(([planId, plan]) => {
              if (userType === 'affiliate' && planId === 'elite') return null;
              
              return (
                <div key={planId} className={`p-3 rounded-lg border-2 ${
                  currentPlan === planId ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                }`}>
                  <h4 className={`font-semibold ${plan.color} text-sm sm:text-base`}>{plan.name}</h4>
                  <p className="text-xs sm:text-sm text-muted-foreground">
                    {plan.price === 0 ? 'Free' : `ZMW ${plan.price}/month`}
                  </p>
                  <p className="text-sm font-bold text-green-600 mt-1">
                    ZMW {plan.commission}/sale
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Monthly earning potential: ZMW {(plan.commission * subscriptionData.currentPeriodSales).toFixed(2)}
                  </p>
                </div>
              );
            })}
          </div>
          <div className="mt-4 text-center">
            <Button onClick={() => setShowPlans(true)} variant="outline" className="text-sm">
              Compare All Features
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SubscriptionManagement;

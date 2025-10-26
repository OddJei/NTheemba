import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { 
  TrendingUp, 
  DollarSign, 
  Target, 
  Calendar,
  ArrowUpCircle,
  ArrowDownCircle
} from "lucide-react";

interface EarningsTrackerProps {
  userType: 'msme' | 'affiliate';
  currentPlan: string;
  monthlyEarnings: number;
  subscriptionCost: number;
  salesCount: number;
  commissionRate: number;
}

const EarningsTracker: React.FC<EarningsTrackerProps> = ({
  userType,
  currentPlan,
  monthlyEarnings,
  subscriptionCost,
  salesCount,
  commissionRate
}) => {
  const breakEvenSales = subscriptionCost > 0 ? Math.ceil(subscriptionCost / commissionRate) : 0;
  const progressToBreakEven = subscriptionCost > 0 ? (salesCount / breakEvenSales) * 100 : 100;
  const netProfit = monthlyEarnings - subscriptionCost;
  const isProfitable = netProfit > 0;

  const planColors = {
    basic: 'text-blue-600',
    pro: 'text-purple-600',
    elite: 'text-yellow-600'
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Current Plan Status */}
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader>
          <CardTitle className="flex items-center justify-between text-lg sm:text-xl">
            <span className={planColors[currentPlan as keyof typeof planColors] || 'text-gray-600'}>
              {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)} Plan
            </span>
            <Badge variant={isProfitable ? "default" : subscriptionCost === 0 ? "secondary" : "destructive"}>
              {subscriptionCost === 0 ? 'Free' : isProfitable ? 'Profitable' : 'Break-even needed'}
            </Badge>
          </CardTitle>
          <CardDescription className="text-sm">
            Your current subscription and performance overview
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 sm:space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Monthly Cost</p>
              <p className="text-lg sm:text-xl font-bold">
                ZMW {subscriptionCost.toFixed(2)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Commission Rate</p>
              <p className="text-lg sm:text-xl font-bold text-green-600">
                ZMW {commissionRate.toFixed(2)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">This Month's Sales</p>
              <p className="text-lg sm:text-xl font-bold">
                {salesCount}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Monthly Earnings</p>
              <p className="text-lg sm:text-xl font-bold text-green-600">
                ZMW {monthlyEarnings.toFixed(2)}
              </p>
            </div>
          </div>

          {/* Break-even Progress */}
          {subscriptionCost > 0 && (
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="font-semibold text-sm sm:text-base">Break-even Progress</h4>
                <span className="text-xs sm:text-sm text-muted-foreground">
                  {salesCount}/{breakEvenSales} sales
                </span>
              </div>
              <Progress value={Math.min(progressToBreakEven, 100)} className="h-2" />
              <p className="text-xs sm:text-sm text-muted-foreground">
                {salesCount >= breakEvenSales
                  ? '🎉 You\'ve covered your subscription cost!'
                  : `${breakEvenSales - salesCount} more sales needed to break even`
                }
              </p>
            </div>
          )}

          {/* Net Profit/Loss */}
          <div className="pt-4 border-t">
            <div className="flex items-center justify-between">
              <span className="font-semibold">Net Profit This Month</span>
              <div className="flex items-center space-x-2">
                {isProfitable ? (
                  <ArrowUpCircle className="w-4 h-4 text-green-600" />
                ) : subscriptionCost === 0 ? (
                  <TrendingUp className="w-4 h-4 text-blue-600" />
                ) : (
                  <ArrowDownCircle className="w-4 h-4 text-red-600" />
                )}
                <span className={`font-bold text-lg ${
                  isProfitable ? 'text-green-600' : 
                  subscriptionCost === 0 ? 'text-blue-600' : 'text-red-600'
                }`}>
                  ZMW {netProfit.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg">
              <Target className="w-5 h-5 text-blue-600" />
              <span>Performance Metrics</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span>Average earnings per sale</span>
              <span className="font-semibold">ZMW {commissionRate.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>ROI this month</span>
              <span className={`font-semibold ${
                subscriptionCost === 0 ? 'text-blue-600' : 
                isProfitable ? 'text-green-600' : 'text-red-600'
              }`}>
                {subscriptionCost === 0 ? 'N/A (Free)' : 
                 `${((netProfit / subscriptionCost) * 100).toFixed(1)}%`}
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>Break-even sales needed</span>
              <span className="font-semibold">
                {subscriptionCost === 0 ? 'N/A' : `${breakEvenSales} sales`}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <span>Growth Potential</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                If you maintain current performance:
              </p>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Annual earnings</span>
                  <span className="font-semibold text-green-600">
                    ZMW {(monthlyEarnings * 12).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Annual profit</span>
                  <span className={`font-semibold ${
                    netProfit > 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    ZMW {(netProfit * 12).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default EarningsTracker;

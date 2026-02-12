import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import FeatureGate from "@/components/ui/feature-gate";
import { useFeatureGate } from "@/lib/feature-gates";
import { 
  AnimatedCounter,
  ProgressRing,
  GradientButton,
  Tooltip,
  StatusDot,
  EmptyState
} from "@/components/ui/enhanced-ui";
import { 
  TrendingUp, 
  Users, 
  DollarSign, 
  Share2,
  Trophy,
  Target,
  Clock,
  CheckCircle,
  AlertCircle,
  Star,
  Zap,
  Gift,
  Activity,
  Eye,
  MessageCircle,
  Bell,
  Crown,
  Heart,
  Handshake
} from "lucide-react";

const AffiliateDashboard = () => {
  const navigate = useNavigate();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [showWelcome, setShowWelcome] = useState(true);

  // Mock user data (in real app, this would come from auth context)
  const user = {
    id: '1',
    tier: 'basic' as const,
    role: 'affiliate' as const,
    subscriptionActive: true,
    trialEndsAt: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000), // 14 days trial
    isUbuntuMember: true, // New Ubuntu community member
    canPromoteOthers: false // Can become true with Ubuntu Pro
  };

  const featureGate = useFeatureGate(user);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const handleUpgrade = () => {
    navigate('/affiliate/subscription-plans');
  };

  const recentActivities = [
    {
      id: 1,
      type: 'click',
      message: 'New click on WhatsApp campaign',
      time: '2 min ago',
      status: 'success'
    },
    {
      id: 2,
      type: 'conversion',
      message: 'Conversion completed - ZMW 250 earned',
      time: '15 min ago',
      status: 'success'
    },
    {
      id: 3,
      type: 'milestone',
      message: 'Reached 1,000 clicks milestone!',
      time: '1 hour ago',
      status: 'achievement'
    }
  ];

  const upcomingPayments = [
    {
      amount: 'ZMW 18,560',
      date: '2024-02-01',
      status: 'pending'
    }
  ];

  const getGreeting = () => {
    const hour = currentTime.getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };
  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      {/* Welcome Alert */}
      {showWelcome && (
        <Alert className="border-blue-200 bg-blue-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Zap className="w-4 h-4 text-blue-600" />
              <AlertDescription className="text-blue-800">
                You're 3 conversions away from reaching your monthly bonus!
              </AlertDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setShowWelcome(false)}>×</Button>
          </div>
        </Alert>
      )}

      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">
            {getGreeting()}, Priya! 
            <Tooltip content="You're performing excellently this month!" className="ml-2">
              <Star className="w-6 h-6 text-yellow-500 inline" />
            </Tooltip>
          </h1>
          <p className="text-muted-foreground text-sm sm:text-base flex items-center space-x-2">
            <StatusDot status="online" />
            <span>Your impact this week</span>
          </p>
        </div>
        <div className="flex space-x-2">
          <GradientButton 
            variant="primary" 
            className="w-full sm:w-auto"
            onClick={() => navigate('/affiliate/campaigns')}
          >
            <Share2 className="w-4 h-4 mr-2" />
            Share Campaign
          </GradientButton>
        </div>
      </div>

      {/* Enhanced Impact Snapshot */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Card className="relative overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              Clicks This Week
              <div className="p-2 bg-blue-100 rounded-lg">
                <Eye className="w-4 h-4 text-blue-600" />
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold">
              <AnimatedCounter value={1247} />
            </div>
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-green-600" />
              <p className="text-xs text-green-600">+15.2% from last week</p>
            </div>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              MSMEs Helped
              <div className="p-2 bg-purple-100 rounded-lg">
                <Users className="w-4 h-4 text-purple-600" />
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold">
              <AnimatedCounter value={23} />
            </div>
            <p className="text-xs text-muted-foreground">Active partnerships</p>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              Earnings To-Date
              <div className="p-2 bg-green-100 rounded-lg">
                <DollarSign className="w-4 h-4 text-green-600" />
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold text-green-600">
              <AnimatedCounter value={18560} prefix="ZMW " />
            </div>
            <p className="text-xs text-muted-foreground">This month</p>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              Monthly Goal
              <div className="p-2 bg-orange-100 rounded-lg">
                <Target className="w-4 h-4 text-orange-600" />
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xl font-bold">74%</span>
              <ProgressRing progress={74} size={60} strokeWidth={6} showValue={false} />
            </div>
            <p className="text-xs text-muted-foreground">ZMW 25,000 target</p>
          </CardContent>
        </Card>
      </div>

      {/* Enhanced Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg sm:text-xl flex items-center space-x-2">
            <Activity className="w-5 h-5" />
            <span>Quick Actions</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <Tooltip content="Share your campaigns on social media">
              <Button 
                className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 text-xs sm:text-sm hover:scale-105 transition-transform"
                onClick={() => navigate('/affiliate/campaigns')}
              >
                <Share2 className="w-5 h-5 sm:w-6 sm:h-6" />
                <span>Share Campaign</span>
              </Button>
            </Tooltip>
            
            <Tooltip content="View detailed performance analytics">
              <Button 
                variant="outline" 
                className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 text-xs sm:text-sm hover:scale-105 transition-transform"
                onClick={() => navigate('/affiliate/earnings')}
              >
                <Target className="w-5 h-5 sm:w-6 sm:h-6" />
                <span>View Performance</span>
              </Button>
            </Tooltip>
            
            <Tooltip content="Request your earned payments">
              <Button 
                variant="outline" 
                className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 text-xs sm:text-sm hover:scale-105 transition-transform"
                onClick={() => navigate('/affiliate/payouts')}
              >
                <DollarSign className="w-5 h-5 sm:w-6 sm:h-6" />
                <span>Request Payout</span>
              </Button>
            </Tooltip>
            
            <Tooltip content="See your ranking among affiliates">
              <Button 
                variant="outline" 
                className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 text-xs sm:text-sm hover:scale-105 transition-transform"
                onClick={() => navigate('/affiliate/leaderboards')}
              >
                <Trophy className="w-5 h-5 sm:w-6 sm:h-6" />
                <span>Leaderboard</span>
              </Button>
            </Tooltip>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity & Upcoming Payments */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center space-x-2">
              <MessageCircle className="w-5 h-5" />
              <span>Recent Activity</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentActivities.map((activity) => (
                <div key={activity.id} className="flex items-center space-x-3 p-3 border rounded-lg">
                  <div className={`p-2 rounded-full ${
                    activity.status === 'success' ? 'bg-green-100' :
                    activity.status === 'achievement' ? 'bg-yellow-100' : 'bg-blue-100'
                  }`}>
                    {activity.status === 'success' ? <CheckCircle className="w-4 h-4 text-green-600" /> :
                     activity.status === 'achievement' ? <Trophy className="w-4 h-4 text-yellow-600" /> :
                     <Activity className="w-4 h-4 text-blue-600" />}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{activity.message}</p>
                    <p className="text-xs text-gray-500 flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{activity.time}</span>
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Upcoming Payments */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center space-x-2">
              <Gift className="w-5 h-5" />
              <span>Upcoming Payments</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {upcomingPayments.length > 0 ? (
              <div className="space-y-3">
                {upcomingPayments.map((payment, index) => (
                  <div key={index} className="p-4 border rounded-lg bg-gradient-to-r from-green-50 to-emerald-50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-2xl font-bold text-green-600">{payment.amount}</span>
                      <Badge variant="secondary">
                        {payment.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600">Expected: {payment.date}</p>
                    <Progress value={85} className="mt-2 h-2" />
                    <p className="text-xs text-gray-500 mt-1">Processing: 85% complete</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<Gift className="w-12 h-12" />}
                title="No pending payments"
                description="Complete more campaigns to earn your next payout!"
                action={
                  <Button variant="outline" onClick={() => navigate('/affiliate/campaigns')}>
                    <Share2 className="w-4 h-4 mr-2" />
                    Start Sharing
                  </Button>
                }
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Ubuntu Community Section */}
      <Card className="mb-6 border-2 border-orange-200 bg-gradient-to-r from-orange-50 to-red-50">
        <CardHeader>
          <CardTitle className="text-lg flex items-center space-x-2">
            <Heart className="w-5 h-5 text-orange-600" />
            <span>Ubuntu Community</span>
            <Badge className="bg-orange-100 text-orange-800">African Unity</Badge>
          </CardTitle>
          <CardDescription>
            Ubuntu: "I am because we are" - Join fellow African entrepreneurs in mutual success
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-white rounded-lg">
              <div className="text-2xl font-bold text-orange-600">156</div>
              <div className="text-sm text-gray-600">Fellow MSMEs</div>
              <div className="text-xs text-gray-500">You can promote</div>
            </div>
            <div className="text-center p-4 bg-white rounded-lg">
              <div className="text-2xl font-bold text-red-600">ZMW 890</div>
              <div className="text-sm text-gray-600">Ubuntu Earnings</div>
              <div className="text-xs text-gray-500">From cross-promotion</div>
            </div>
            <div className="text-center p-4 bg-white rounded-lg">
              <div className="text-2xl font-bold text-green-600">12</div>
              <div className="text-sm text-gray-600">Businesses Helped</div>
              <div className="text-xs text-gray-500">Ubuntu spirit</div>
            </div>
          </div>
          
          <div className="mt-4 flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-4">
            <Button 
              className="bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600"
              onClick={() => navigate('/ubuntu-community')}
            >
              <Users className="w-4 h-4 mr-2" />
              Join Ubuntu Community
            </Button>
            {user.canPromoteOthers ? (
              <Button variant="outline">
                <Handshake className="w-4 h-4 mr-2" />
                Promote Fellow MSMEs
              </Button>
            ) : (
              <Button 
                variant="outline"
                onClick={() => navigate('/affiliate/subscription-plans')}
              >
                <Crown className="w-4 h-4 mr-2" />
                Upgrade to Promote Others
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Feature-Gated Pro Features */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Advanced Analytics - Pro Feature */}
        <FeatureGate
          featureId="ADVANCED_ANALYTICS"
          user={user}
          upgradePromptVariant="card"
          onUpgrade={handleUpgrade}
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center space-x-2">
                <TrendingUp className="w-5 h-5 text-green-600" />
                <span>Advanced Analytics</span>
                <Badge variant="secondary" className="ml-auto">Pro</Badge>
              </CardTitle>
              <CardDescription>
                Detailed conversion funnels and audience insights
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Conversion Rate</span>
                  <span className="font-bold text-green-600">12.4%</span>
                </div>
                <Progress value={12.4} className="h-2" />
                
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="text-center">
                    <div className="text-xl font-bold">65%</div>
                    <div className="text-xs text-gray-500">Mobile Users</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold">35%</div>
                    <div className="text-xs text-gray-500">Desktop Users</div>
                  </div>
                </div>

                <Button variant="outline" className="w-full mt-4">
                  <Eye className="w-4 h-4 mr-2" />
                  View Detailed Report
                </Button>
              </div>
            </CardContent>
          </Card>
        </FeatureGate>

        {/* Pro Campaigns - Pro Feature */}
        <FeatureGate
          featureId="PRO_CAMPAIGNS"
          user={user}
          upgradePromptVariant="card"
          onUpgrade={handleUpgrade}
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center space-x-2">
                <Star className="w-5 h-5 text-purple-600" />
                <span>Pro-Only Campaigns</span>
                <Badge variant="secondary" className="ml-auto bg-purple-100 text-purple-800">
                  Exclusive
                </Badge>
              </CardTitle>
              <CardDescription>
                Access high-commission exclusive campaigns
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="p-3 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">Premium Electronics Campaign</span>
                    <Badge className="bg-purple-600 text-white">15% Commission</Badge>
                  </div>
                  <p className="text-xs text-gray-600">Electronics & Gadgets • Ends in 5 days</p>
                </div>
                
                <div className="p-3 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">Luxury Fashion Campaign</span>
                    <Badge className="bg-green-600 text-white">12% Commission</Badge>
                  </div>
                  <p className="text-xs text-gray-600">Fashion & Lifestyle • Ends in 3 days</p>
                </div>

                <Button className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700">
                  <Star className="w-4 h-4 mr-2" />
                  Browse Pro Campaigns
                </Button>
              </div>
            </CardContent>
          </Card>
        </FeatureGate>
      </div>

      {/* Upgrade Banner for Basic Users */}
      {user.tier === 'basic' && (
        <Card className="border-2 border-green-200 bg-gradient-to-r from-green-50 via-emerald-50 to-green-50">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-green-100 rounded-full">
                  <Crown className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h3 className="font-bold text-lg">Unlock Your Full Potential</h3>
                  <p className="text-gray-600">
                    Upgrade to Pro for exclusive campaigns, higher commissions, and weekly payouts
                  </p>
                  <div className="flex items-center space-x-4 mt-2 text-sm text-gray-600">
                    <span className="flex items-center">
                      <Zap className="w-4 h-4 mr-1 text-yellow-500" />
                      10-15% commission rates
                    </span>
                    <span className="flex items-center">
                      <Star className="w-4 h-4 mr-1 text-purple-500" />
                      Pro-only campaigns
                    </span>
                    <span className="flex items-center">
                      <DollarSign className="w-4 h-4 mr-1 text-green-500" />
                      Weekly payouts
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end space-y-2">
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-600">ZMW 99</div>
                  <div className="text-sm text-gray-500">/month</div>
                </div>
                <Button 
                  className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                  onClick={handleUpgrade}
                >
                  Upgrade Now
                  <Crown className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default AffiliateDashboard;
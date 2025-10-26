import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  DollarSign, 
  TrendingUp, 
  Target, 
  Users, 
  Calendar,
  Filter,
  Download,
  Eye,
  Clock,
  CheckCircle,
  AlertCircle,
  BarChart3,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  Wallet,
  CreditCard,
  Gift,
  Zap
} from 'lucide-react';

const AffiliateEarnings = () => {
  const [timeRange, setTimeRange] = useState('30d');
  const [earningsFilter, setEarningsFilter] = useState('all');

  // Mock earnings data
  const earningsOverview = {
    totalEarned: 15247.83,
    thisMonth: 3421.50,
    pendingEarnings: 892.25,
    availableForWithdrawal: 14355.58,
    conversionRate: 12.4,
    averageCommission: 45.30,
    totalReferrals: 1247,
    activeReferrals: 892
  };

  const monthlyTrend = [
    { month: 'Jan', earnings: 2150, referrals: 45 },
    { month: 'Feb', earnings: 2890, referrals: 67 },
    { month: 'Mar', earnings: 3420, referrals: 89 },
    { month: 'Apr', earnings: 2960, referrals: 72 },
    { month: 'May', earnings: 4180, referrals: 105 },
    { month: 'Jun', earnings: 3650, referrals: 94 }
  ];

  const recentEarnings = [
    { id: 1, type: 'commission', description: 'Commission from John Doe purchase', amount: 125.50, date: '2025-09-01', status: 'confirmed', referralId: 'REF-2025-001' },
    { id: 2, type: 'bonus', description: 'Monthly performance bonus', amount: 500.00, date: '2025-08-31', status: 'confirmed', referralId: 'BONUS-AUG' },
    { id: 3, type: 'commission', description: 'Commission from Sarah Smith purchase', amount: 87.25, date: '2025-08-30', status: 'pending', referralId: 'REF-2025-002' },
    { id: 4, type: 'tier_bonus', description: 'Tier upgrade bonus', amount: 250.00, date: '2025-08-29', status: 'confirmed', referralId: 'TIER-GOLD' },
    { id: 5, type: 'commission', description: 'Commission from Mike Johnson purchase', amount: 96.80, date: '2025-08-28', status: 'confirmed', referralId: 'REF-2025-003' }
  ];

  const commissionTiers = [
    { tier: 'Bronze', minReferrals: 0, maxReferrals: 49, rate: '5%', color: 'bg-amber-100 text-amber-800', current: false },
    { tier: 'Silver', minReferrals: 50, maxReferrals: 149, rate: '7.5%', color: 'bg-gray-100 text-gray-800', current: false },
    { tier: 'Gold', minReferrals: 150, maxReferrals: 299, rate: '10%', color: 'bg-yellow-100 text-yellow-800', current: true },
    { tier: 'Platinum', minReferrals: 300, maxReferrals: 499, rate: '12.5%', color: 'bg-purple-100 text-purple-800', current: false },
    { tier: 'Diamond', minReferrals: 500, maxReferrals: null, rate: '15%', color: 'bg-blue-100 text-blue-800', current: false }
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'confirmed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'commission':
        return <DollarSign className="w-4 h-4 text-green-500" />;
      case 'bonus':
        return <Gift className="w-4 h-4 text-purple-500" />;
      case 'tier_bonus':
        return <Zap className="w-4 h-4 text-blue-500" />;
      default:
        return <Wallet className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Earnings & Commissions</h1>
          <p className="text-muted-foreground text-sm sm:text-base">
            Track your affiliate performance and commission earnings
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button variant="outline" className="w-full sm:w-auto">
            <Download className="w-4 h-4 mr-2" />
            Export Report
          </Button>
          <Button className="w-full sm:w-auto">
            <Eye className="w-4 h-4 mr-2" />
            Request Payout
          </Button>
        </div>
      </div>

      {/* Earnings Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Earned</p>
                <p className="text-2xl font-bold">ZMW {earningsOverview.totalEarned.toLocaleString()}</p>
                <p className="text-xs text-green-600 flex items-center mt-1">
                  <ArrowUpRight className="w-3 h-3 mr-1" />
                  +12.4% vs last month
                </p>
              </div>
              <div className="h-12 w-12 bg-green-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">This Month</p>
                <p className="text-2xl font-bold">ZMW {earningsOverview.thisMonth.toLocaleString()}</p>
                <p className="text-xs text-blue-600 flex items-center mt-1">
                  <Target className="w-3 h-3 mr-1" />
                  68% of monthly goal
                </p>
              </div>
              <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Available</p>
                <p className="text-2xl font-bold">ZMW {earningsOverview.availableForWithdrawal.toLocaleString()}</p>
                <p className="text-xs text-purple-600 flex items-center mt-1">
                  <Wallet className="w-3 h-3 mr-1" />
                  Ready for withdrawal
                </p>
              </div>
              <div className="h-12 w-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <CreditCard className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Conversion Rate</p>
                <p className="text-2xl font-bold">{earningsOverview.conversionRate}%</p>
                <p className="text-xs text-orange-600 flex items-center mt-1">
                  <Users className="w-3 h-3 mr-1" />
                  {earningsOverview.activeReferrals} active referrals
                </p>
              </div>
              <div className="h-12 w-12 bg-orange-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-1 sm:grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="tiers">Commission Tiers</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Button variant="outline" className="h-20 flex flex-col">
                  <Download className="w-6 h-6 mb-2" />
                  <span>Download Statement</span>
                </Button>
                <Button variant="outline" className="h-20 flex flex-col">
                  <Target className="w-6 h-6 mb-2" />
                  <span>Set Monthly Goal</span>
                </Button>
                <Button variant="outline" className="h-20 flex flex-col">
                  <BarChart3 className="w-6 h-6 mb-2" />
                  <span>Performance Report</span>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Monthly Performance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                6-Month Performance Trend
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-medium mb-3">Earnings by Month</h3>
                  <div className="space-y-2">
                    {monthlyTrend.map((month, index) => (
                      <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                        <span className="text-sm font-medium">{month.month}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-sm">ZMW {month.earnings.toLocaleString()}</span>
                          <Progress 
                            value={(month.earnings / 5000) * 100} 
                            className="w-20 h-2" 
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="font-medium mb-3">Referrals by Month</h3>
                  <div className="space-y-2">
                    {monthlyTrend.map((month, index) => (
                      <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                        <span className="text-sm font-medium">{month.month}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-sm">{month.referrals} referrals</span>
                          <Progress 
                            value={(month.referrals / 120) * 100} 
                            className="w-20 h-2" 
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Transactions Tab */}
        <TabsContent value="transactions" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Recent Transactions</CardTitle>
              <div className="flex gap-2">
                <Select value={timeRange} onValueChange={setTimeRange}>
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7d">Last 7 days</SelectItem>
                    <SelectItem value="30d">Last 30 days</SelectItem>
                    <SelectItem value="90d">Last 90 days</SelectItem>
                    <SelectItem value="1y">Last year</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={earningsFilter} onValueChange={setEarningsFilter}>
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="commission">Commission</SelectItem>
                    <SelectItem value="bonus">Bonus</SelectItem>
                    <SelectItem value="tier_bonus">Tier Bonus</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {recentEarnings.map((earning) => (
                  <div key={earning.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50">
                    <div className="flex items-center gap-3">
                      {getTypeIcon(earning.type)}
                      <div>
                        <p className="font-medium text-sm">{earning.description}</p>
                        <p className="text-xs text-muted-foreground">
                          {earning.date} • {earning.referralId}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="font-bold text-green-600">ZMW {earning.amount}</p>
                        <div className="flex items-center gap-1">
                          {getStatusIcon(earning.status)}
                          <span className="text-xs capitalize">{earning.status}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Commission Tiers Tab */}
        <TabsContent value="tiers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="w-5 h-5" />
                Commission Tiers & Progress
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {commissionTiers.map((tier, index) => (
                  <div key={index} className={`p-4 border-2 rounded-lg ${tier.current ? 'border-blue-200 bg-blue-50' : 'border-gray-200'}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <Badge className={tier.color}>{tier.tier}</Badge>
                        <span className="font-medium">{tier.rate} Commission Rate</span>
                        {tier.current && <Badge variant="secondary">Current Tier</Badge>}
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {tier.minReferrals}-{tier.maxReferrals || '∞'} referrals
                      </span>
                    </div>
                    {tier.current && (
                      <div className="mt-3">
                        <div className="flex justify-between text-sm mb-1">
                          <span>Progress to {commissionTiers[index + 1]?.tier || 'Max Tier'}</span>
                          <span>{earningsOverview.totalReferrals}/{commissionTiers[index + 1]?.minReferrals || 500}</span>
                        </div>
                        <Progress 
                          value={(earningsOverview.totalReferrals / (commissionTiers[index + 1]?.minReferrals || 500)) * 100} 
                          className="h-2"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PieChart className="w-5 h-5" />
                  Earnings Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                    <span className="text-sm font-medium">Commissions</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">ZMW 12,450</span>
                      <Badge variant="secondary">82%</Badge>
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                    <span className="text-sm font-medium">Bonuses</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">ZMW 2,100</span>
                      <Badge variant="secondary">14%</Badge>
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                    <span className="text-sm font-medium">Tier Bonuses</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">ZMW 697</span>
                      <Badge variant="secondary">4%</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Key Performance Metrics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Average Order Value</span>
                      <span className="font-bold">ZMW 453.20</span>
                    </div>
                    <Progress value={75} className="h-2" />
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Referral Success Rate</span>
                      <span className="font-bold">68.4%</span>
                    </div>
                    <Progress value={68.4} className="h-2" />
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Customer Lifetime Value</span>
                      <span className="font-bold">ZMW 1,247.80</span>
                    </div>
                    <Progress value={82} className="h-2" />
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Repeat Purchase Rate</span>
                      <span className="font-bold">34.2%</span>
                    </div>
                    <Progress value={34.2} className="h-2" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AffiliateEarnings;
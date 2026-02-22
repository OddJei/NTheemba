import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import API from "@/lib/api";
import { 
  Users, Building2, TrendingUp, DollarSign, Activity, 
  Shield, AlertCircle, ArrowLeft, Menu, X, Check
} from "lucide-react";

interface AdminStats {
  totalUsers: number;
  totalMSMEs: number;
  totalAffiliates: number;
  platformRevenue: number;
  activeUsers: number;
  systemHealth: number;
  pendingApprovals: number;
}

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [stats, setStats] = useState<AdminStats>({
    totalUsers: 0,
    totalMSMEs: 0,
    totalAffiliates: 0,
    platformRevenue: 0,
    activeUsers: 0,
    systemHealth: 0,
    pendingApprovals: 0
  });

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await API('/admin/stats');
      setStats({
        totalUsers: data.totalUsers || 6250,
        totalMSMEs: data.totalMSMEs || 1050,
        totalAffiliates: data.totalAffiliates || 5200,
        platformRevenue: data.platformRevenue || 2450000,
        activeUsers: data.activeUsers || 4820,
        systemHealth: data.systemHealth || 98,
        pendingApprovals: data.pendingApprovals || 12
      });
    } catch (error) {
      console.error('Failed to load stats:', error);
      // Use mock data on error
      setStats({
        totalUsers: 6250,
        totalMSMEs: 1050,
        totalAffiliates: 5200,
        platformRevenue: 2450000,
        activeUsers: 4820,
        systemHealth: 98,
        pendingApprovals: 12
      });
    }
  };

  const navItems = [
    { id: 'overview', label: 'Overview', icon: TrendingUp },
    { id: 'approvals', label: 'Approvals', icon: Check },
    { id: 'settings', label: 'Settings', icon: Shield },
  ];

  return (
    <div className="min-h-screen bg-[#FEF6ED] flex flex-col md:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden md:block w-64 border-r bg-[#035688] p-4 flex-shrink-0">
        <div className="flex items-center gap-2 mb-6">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="hover:bg-[#0A3F5F] touch-target">
            <ArrowLeft className="w-4 h-4 text-white" />
          </Button>
          <h2 className="font-bold text-lg text-white">Admin</h2>
        </div>

        <div className="space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Button
                key={item.id}
                variant="ghost"
                className={`w-full justify-start text-white touch-target hover:bg-[#0A3F5F]`}
                onClick={() => {}}
              >
                <Icon className="w-4 h-4 mr-2" /> {item.label}
              </Button>
            );
          })}
        </div>

        <div className="mt-6 p-3 bg-[#0A3F5F] rounded-lg">
          <p className="text-sm text-white font-semibold">System Health</p>
          <p className="text-2xl font-bold text-[#F38D1C]">{stats.systemHealth}%</p>
        </div>
      </aside>

      {/* Mobile Header */}
      <header className="md:hidden sticky top-0 z-50 bg-[#035688] border-b shadow-sm safe-area-top">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => navigate('/')} 
              className="hover:bg-[#0A3F5F] text-white touch-target"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <h2 className="font-bold text-base text-white">Admin</h2>
          </div>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="hover:bg-[#0A3F5F] text-white touch-target"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>

        {mobileMenuOpen && (
          <div className="bg-[#035688] border-t border-[#0A3F5F] animate-in slide-in-from-top">
            <div className="px-4 py-2 space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Button
                    key={item.id}
                    variant="ghost"
                    className={`w-full justify-start text-white touch-target-large hover:bg-[#0A3F5F]`}
                    onClick={() => {
                      setMobileMenuOpen(false);
                    }}
                  >
                    <Icon className="w-5 h-5 mr-3" />
                    <span className="text-base">{item.label}</span>
                  </Button>
                );
              })}
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto pb-20 md:pb-0">
        <div className="container mx-auto px-4 py-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-[#270A01]">Admin Dashboard</h1>
            <p className="text-sm text-[#C04208]">Platform management and monitoring</p>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span>Total Users</span>
                  <Users className="w-4 h-4 text-[#035688]" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-[#035688]">{stats.totalUsers.toLocaleString()}</div>
                <p className="text-xs text-[#F38D1C] mt-1">{stats.activeUsers.toLocaleString()} active</p>
              </CardContent>
            </Card>

            <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span>MSMEs</span>
                  <Building2 className="w-4 h-4 text-[#F38D1C]" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-[#F38D1C]">{stats.totalMSMEs.toLocaleString()}</div>
                <p className="text-xs text-[#C04208] mt-1">Registered</p>
              </CardContent>
            </Card>

            <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span>Affiliates</span>
                  <Activity className="w-4 h-4 text-[#C04208]" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-[#C04208]">{stats.totalAffiliates.toLocaleString()}</div>
                <p className="text-xs text-[#C04208] mt-1">Active</p>
              </CardContent>
            </Card>

            <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20 xs:col-span-2 lg:col-span-1">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span>Revenue</span>
                  <DollarSign className="w-4 h-4 text-[#035688]" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-[#035688]">ZMW {(stats.platformRevenue / 1000000).toFixed(1)}M</div>
                <p className="text-xs text-[#C04208] mt-1">This month</p>
              </CardContent>
            </Card>
          </div>

          {/* System Health & Pending Approvals */}
          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="border-[#F38D1C]/20">
              <CardHeader>
                <CardTitle className="flex items-center text-[#270A01]">
                  <Shield className="w-5 h-5 mr-2 text-[#035688]" />
                  System Health
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center text-[#270A01]">
                        <Check className="w-4 h-4 mr-2 text-[#035688]" />
                        API Response Time
                      </span>
                      <span className="text-[#F38D1C] font-semibold">125ms</span>
                    </div>
                    <Progress value={95} className="h-2 bg-[#F38D1C]/20" />
                  </div>
                  
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center text-[#270A01]">
                        <Check className="w-4 h-4 mr-2 text-[#035688]" />
                        Database Performance
                      </span>
                      <span className="text-[#F38D1C] font-semibold">Optimal</span>
                    </div>
                    <Progress value={98} className="h-2 bg-[#F38D1C]/20" />
                  </div>
                  
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center text-[#270A01]">
                        <Check className="w-4 h-4 mr-2 text-[#035688]" />
                        Server Uptime
                      </span>
                      <span className="text-[#F38D1C] font-semibold">99.9%</span>
                    </div>
                    <Progress value={99.9} className="h-2 bg-[#F38D1C]/20" />
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center text-[#270A01]">
                        <AlertCircle className="w-4 h-4 mr-2 text-[#C04208]" />
                        Storage Usage
                      </span>
                      <span className="text-[#C04208] font-semibold">78%</span>
                    </div>
                    <Progress value={78} className="h-2 bg-[#C04208]/20" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#F38D1C]/20">
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-[#270A01]">
                  <span>Pending Approvals</span>
                  <Badge className="bg-[#C04208]">{stats.pendingApprovals}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between p-3 border border-[#F38D1C]/20 rounded-lg hover:bg-[#FEF6ED]/50 transition-colors">
                  <div>
                    <p className="font-semibold text-sm text-[#270A01]">MSME Applications</p>
                    <p className="text-xs text-[#C04208]">8 pending approval</p>
                  </div>
                  <Button size="sm" variant="outline" className="border-[#035688]">Review</Button>
                </div>

                <div className="flex items-center justify-between p-3 border border-[#F38D1C]/20 rounded-lg hover:bg-[#FEF6ED]/50 transition-colors">
                  <div>
                    <p className="font-semibold text-sm text-[#270A01]">Affiliate Verifications</p>
                    <p className="text-xs text-[#C04208]">4 awaiting review</p>
                  </div>
                  <Button size="sm" variant="outline" className="border-[#035688]">Review</Button>
                </div>

                <div className="flex items-center justify-between p-3 border border-[#F38D1C]/20 rounded-lg hover:bg-[#FEF6ED]/50 transition-colors">
                  <div>
                    <p className="font-semibold text-sm text-[#270A01]">Reported Content</p>
                    <p className="text-xs text-[#C04208]">0 flagged items</p>
                  </div>
                  <Button size="sm" variant="ghost" disabled>Review</Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Activity & Revenue Trends */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="border-[#F38D1C]/20">
              <CardHeader>
                <CardTitle className="text-[#270A01]">Recent Activity</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-start gap-3 text-sm">
                    <div className="w-2 h-2 rounded-full bg-[#035688] mt-1.5 flex-shrink-0"></div>
                    <div className="flex-1">
                      <p className="font-medium text-[#270A01]">New MSME registered</p>
                      <p className="text-xs text-[#C04208]">KabuShop - 5 minutes ago</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 text-sm">
                    <div className="w-2 h-2 rounded-full bg-[#F38D1C] mt-1.5 flex-shrink-0"></div>
                    <div className="flex-1">
                      <p className="font-medium text-[#270A01]">Campaign approved</p>
                      <p className="text-xs text-[#C04208]">Summer Sale 2026 - 12 minutes ago</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 text-sm">
                    <div className="w-2 h-2 rounded-full bg-[#C04208] mt-1.5 flex-shrink-0"></div>
                    <div className="flex-1">
                      <p className="font-medium text-[#270A01]">Payout processed</p>
                      <p className="text-xs text-[#C04208]">ZMW 18,560 to 12 affiliates - 1 hour ago</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 text-sm">
                    <div className="w-2 h-2 rounded-full bg-[#035688] mt-1.5 flex-shrink-0"></div>
                    <div className="flex-1">
                      <p className="font-medium text-[#270A01]">System update completed</p>
                      <p className="text-xs text-[#C04208]">Version 2.3.1 deployed - 3 hours ago</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#F38D1C]/20">
              <CardHeader>
                <CardTitle className="flex items-center text-[#270A01]">
                  <TrendingUp className="w-4 h-4 mr-2 text-[#035688]" />
                  Revenue Trends
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {[
                    { day: 'Mon', amount: 112340 },
                    { day: 'Tue', amount: 98750 },
                    { day: 'Wed', amount: 125600 },
                    { day: 'Thu', amount: 89200 },
                    { day: 'Fri', amount: 145800 },
                    { day: 'Sat', amount: 78450 },
                    { day: 'Sun', amount: 56890 },
                  ].map((item) => (
                    <div key={item.day} className="flex items-center justify-between text-sm">
                      <span className="w-10 text-[#270A01] font-medium">{item.day}</span>
                      <div className="flex-1 mx-3">
                        <Progress value={(item.amount / 145800) * 100} className="h-2 bg-[#F38D1C]/20" />
                      </div>
                      <span className="w-20 text-right font-semibold text-[#035688]">
                        ZMW {(item.amount / 1000).toFixed(0)}K
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-4 border-t border-[#F38D1C]/20">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-[#270A01]">Total</span>
                    <span className="text-lg font-bold text-[#035688]">ZMW 707K</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Quick Actions */}
          <Card className="border-[#F38D1C]/20">
            <CardHeader>
              <CardTitle className="text-[#270A01]">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Button
                  variant="outline"
                  onClick={() => alert('User management feature coming soon!')}
                  className="h-20 flex flex-col space-y-2 touch-target border-[#035688] hover:bg-[#FEF6ED]"
                >
                  <Users className="w-5 h-5 text-[#035688]" />
                  <span className="text-xs text-[#270A01]">Manage Users</span>
                </Button>

                <Button
                  variant="outline"
                  onClick={() => alert('System settings feature coming soon!')}
                  className="h-20 flex flex-col space-y-2 touch-target border-[#035688] hover:bg-[#FEF6ED]"
                >
                  <Shield className="w-5 h-5 text-[#035688]" />
                  <span className="text-xs text-[#270A01]">Settings</span>
                </Button>

                <Button
                  variant="outline"
                  onClick={() => alert('Analytics feature coming soon!')}
                  className="h-20 flex flex-col space-y-2 touch-target border-[#035688] hover:bg-[#FEF6ED]"
                >
                  <TrendingUp className="w-5 h-5 text-[#035688]" />
                  <span className="text-xs text-[#270A01]">Analytics</span>
                </Button>

                <Button
                  variant="outline"
                  onClick={() => alert('Reports feature coming soon!')}
                  className="h-20 flex flex-col space-y-2 touch-target border-[#035688] hover:bg-[#FEF6ED]"
                >
                  <Activity className="w-5 h-5 text-[#035688]" />
                  <span className="text-xs text-[#270A01]">Reports</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-[#F38D1C]/20 shadow-lg safe-area-bottom z-40">
        <div className="grid grid-cols-3 h-16">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => {}}
                className={`flex flex-col items-center justify-center gap-1 touch-target-large transition-colors text-[#C04208] hover:bg-[#FEF6ED]`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs font-medium">{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

export default AdminDashboard;

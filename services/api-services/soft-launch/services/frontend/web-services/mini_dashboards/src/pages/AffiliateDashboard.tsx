import { useEffect, useState, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import API from "@/lib/api";
import {
  Users, DollarSign, Eye, Target, ArrowLeft,
  LayoutDashboard, ShoppingBag, Trophy, Search, Link as LinkIcon,
  Menu, X
} from "lucide-react";

interface AffiliateStats {
  clicksThisWeek: number;
  msmesHelped: number;
  earningsToDate: number;
  monthlyGoal: number;
  monthlyGoalProgress: number;
}

interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  msmeName: string;
  commissionRate: number;
}

interface LeaderboardEntry {
  rank: number;
  id: string;
  name: string;
  earnings: number;
  conversions: number;
}

const AffiliateDashboard = () => {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState<string>('dashboard');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [stats, setStats] = useState<AffiliateStats>({
    clicksThisWeek: 0,
    msmesHelped: 0,
    earningsToDate: 0,
    monthlyGoal: 25000,
    monthlyGoalProgress: 0
  });
  const [products, setProducts] = useState<Product[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  useEffect(() => {
    loadStats();
    loadProducts();
    loadLeaderboard();
  }, []);

  useEffect(() => {
    filterProducts();
  }, [searchQuery, selectedCategory, products]);

  const loadStats = async () => {
    try {
      const data = await API('/affiliate/stats');
      setStats({
        clicksThisWeek: data.clicksThisWeek || 1247,
        msmesHelped: data.msmesHelped || 23,
        earningsToDate: data.earningsToDate || 18560,
        monthlyGoal: data.monthlyGoal || 25000,
        monthlyGoalProgress: data.monthlyGoalProgress || 74
      });
    } catch (error) {
      setStats({ clicksThisWeek: 1247, msmesHelped: 23, earningsToDate: 18560, monthlyGoal: 25000, monthlyGoalProgress: 74 });
    }
  };

  const loadProducts = async () => {
    try {
      const data = await API('/affiliate/products');
      setProducts(data);
    } catch (error) {
      setProducts([
        { id: '1', name: 'Handmade Soap', description: 'Natural organic soap', price: 25, category: 'Beauty', msmeName: 'Zam Beauty', commissionRate: 15 },
        { id: '2', name: 'Coffee Beans 1kg', description: 'Premium arabica', price: 120, category: 'Food', msmeName: 'Lusaka Coffee', commissionRate: 20 },
        { id: '3', name: 'Leather Wallet', description: 'Handcrafted wallet', price: 180, category: 'Fashion', msmeName: 'Craft Corner', commissionRate: 18 },
        { id: '4', name: 'Wooden Table', description: 'Solid oak table', price: 2500, category: 'Furniture', msmeName: 'Wood Works', commissionRate: 12 },
        { id: '5', name: 'Herbal Tea Set', description: 'Traditional blend', price: 65, category: 'Food', msmeName: 'ZamTea', commissionRate: 22 },
        { id: '6', name: 'Canvas Bag', description: 'Eco-friendly tote', price: 45, category: 'Fashion', msmeName: 'Green Bags', commissionRate: 17 }
      ]);
    }
  };

  const loadLeaderboard = async () => {
    try {
      const data = await API('/affiliate/leaderboard');
      setLeaderboard(data);
    } catch (error) {
      setLeaderboard([
        { rank: 1, id: '1', name: 'Priya Sharma', earnings: 45230, conversions: 234 },
        { rank: 2, id: '2', name: 'James Banda', earnings: 38950, conversions: 198 },
        { rank: 3, id: '3', name: 'Sarah Mwale', earnings: 32100, conversions: 176 },
        { rank: 4, id: '4', name: 'Michael Chen', earnings: 28750, conversions: 145 },
        { rank: 5, id: '5', name: 'Grace Phiri', earnings: 24680, conversions: 132 },
        { rank: 6, id: '6', name: 'You (Priya)', earnings: 18560, conversions: 92 }
      ]);
    }
  };

  const filterProducts = () => {
    let filtered = products;
    if (searchQuery) {
      filtered = filtered.filter(p =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.msmeName.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(p => p.category === selectedCategory);
    }
    setFilteredProducts(filtered);
  };

  const handleCreateLink = async (product: Product) => {
    try {
      const data = await API('/affiliate/links/generate', {
        method: 'POST',
        body: JSON.stringify({ productId: product.id })
      });
      const link = data.link || `https://ntheemba.com/ref/${product.id}/priya`;
      navigator.clipboard.writeText(link);
      alert('Link copied!');
    } catch (error) {
      const link = `https://ntheemba.com/ref/${product.id}/priya`;
      navigator.clipboard.writeText(link);
      alert('Link copied!');
    }
  };

  const categories = ['all', ...Array.from(new Set(products.map(p => p.category)))];

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'products', label: 'Products', icon: ShoppingBag },
    { id: 'leaderboard', label: 'Leaderboard', icon: Trophy },
  ];

  return (
    <div className="min-h-screen bg-[#FEF6ED] flex flex-col md:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:flex-col w-64 h-screen sticky top-0 border-r bg-[#035688] p-4 flex-shrink-0">
        <div className="flex items-center gap-2 mb-6">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="hover:bg-[#0A3F5F] touch-target">
            <ArrowLeft className="w-4 h-4 text-white" />
          </Button>
          <h2 className="font-bold text-lg text-white">Affiliate</h2>
        </div>

        <div className="space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Button
                key={item.id}
                variant={activeSection === item.id ? 'default' : 'ghost'}
                className={`w-full justify-start text-white touch-target ${
                  activeSection === item.id ? 'bg-[#F38D1C] hover:bg-[#E67E10]' : 'hover:bg-[#0A3F5F]'
                }`}
                onClick={() => setActiveSection(item.id)}
              >
                <Icon className="w-4 h-4 mr-2" /> {item.label}
              </Button>
            );
          })}
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
            <h2 className="font-bold text-base text-white">Affiliate</h2>
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

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="bg-[#035688] border-t border-[#0A3F5F] animate-in slide-in-from-top">
            <div className="px-4 py-2 space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Button
                    key={item.id}
                    variant="ghost"
                    className={`w-full justify-start text-white touch-target-large ${
                      activeSection === item.id ? 'bg-[#F38D1C]' : 'hover:bg-[#0A3F5F]'
                    }`}
                    onClick={() => {
                      setActiveSection(item.id);
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
          {activeSection === 'dashboard' && (
            <>
              <div>
                <h1 className="text-2xl font-bold text-[#270A01]">Dashboard</h1>
                <p className="text-sm text-[#C04208]">Your performance overview</p>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      <span>Clicks</span>
                      <Eye className="w-4 h-4 text-[#035688]" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#035688]">{stats.clicksThisWeek.toLocaleString()}</div>
                    <p className="text-xs text-[#C04208] mt-1">This week</p>
                  </CardContent>
                </Card>

                <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      <span>MSMEs Helped</span>
                      <Users className="w-4 h-4 text-[#F38D1C]" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#F38D1C]">{stats.msmesHelped}</div>
                    <p className="text-xs text-[#C04208] mt-1">Partnerships</p>
                  </CardContent>
                </Card>

                <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      <span>Earnings</span>
                      <DollarSign className="w-4 h-4 text-[#C04208]" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#C04208]">ZMW {stats.earningsToDate.toLocaleString()}</div>
                    <p className="text-xs text-[#C04208] mt-1">This month</p>
                  </CardContent>
                </Card>

                <Card className="hover:shadow-md transition-shadow border-[#F38D1C]/20 xs:col-span-2 lg:col-span-1">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      <span>Goal</span>
                      <Target className="w-4 h-4 text-[#035688]" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-[#035688]">{stats.monthlyGoalProgress}%</div>
                    <Progress value={stats.monthlyGoalProgress} className="my-2 h-2 bg-[#F38D1C]/20" />
                    <p className="text-xs text-[#C04208]">ZMW {stats.monthlyGoal.toLocaleString()} target</p>
                  </CardContent>
                </Card>
              </div>

              {/* Active Campaigns */}
              <Card className="border-[#F38D1C]/20">
                <CardHeader>
                  <CardTitle className="text-[#270A01]">Active Campaigns</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center p-3 border border-[#F38D1C]/20 rounded-lg">
                      <div>
                        <h3 className="font-semibold text-[#270A01]">Summer Sale 2026</h3>
                        <p className="text-sm text-[#C04208]">234 clicks • 12 conversions</p>
                      </div>
                      <Badge className="bg-[#F38D1C] text-white">Active</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {activeSection === 'products' && (
            <>
              <div>
                <h1 className="text-2xl font-bold text-[#270A01]">Browse Products</h1>
                <p className="text-sm text-[#C04208]">Create affiliate links for these products</p>
              </div>

              {/* Search & Filters */}
              <div className="flex flex-col gap-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#C04208] w-4 h-4" />
                  <Input 
                    placeholder="Search products..." 
                    value={searchQuery} 
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)} 
                    className="pl-10"
                  />
                </div>

                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                  {categories.map(cat => (
                    <Button 
                      key={cat} 
                      variant={selectedCategory === cat ? 'default' : 'outline'} 
                      size="sm" 
                      onClick={() => setSelectedCategory(cat)}
                      className={selectedCategory === cat ? 'bg-[#035688]' : 'border-[#C04208]'}
                    >
                      {cat}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Products Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredProducts.map(product => (
                  <Card key={product.id} className="hover:shadow-lg transition-shadow border-[#F38D1C]/20">
                    <CardHeader>
                      <div className="flex justify-between items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <CardTitle className="text-base truncate text-[#270A01]">{product.name}</CardTitle>
                          <p className="text-xs text-[#C04208] truncate">{product.msmeName}</p>
                        </div>
                        <Badge className="bg-[#F38D1C] text-white flex-shrink-0">{product.category}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm text-[#C04208] line-clamp-2">{product.description}</p>
                      <div>
                        <p className="text-xl font-bold text-[#035688]">ZMW {product.price}</p>
                        <p className="text-xs text-[#F38D1C]">Earn {product.commissionRate}%</p>
                      </div>
                      <Button 
                        className="w-full bg-[#035688] hover:bg-[#0A3F5F]"
                        onClick={() => handleCreateLink(product)}
                      >
                        <LinkIcon className="w-4 h-4 mr-2" /> 
                        Create Link
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}

          {activeSection === 'leaderboard' && (
            <>
              <div>
                <h1 className="text-2xl font-bold text-[#270A01]">Leaderboard</h1>
                <p className="text-sm text-[#C04208]">Top performing affiliates</p>
              </div>

              <Card className="border-[#F38D1C]/20">
                <CardHeader>
                  <CardTitle className="text-[#270A01]">Top Affiliates</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {leaderboard.map((entry, idx) => (
                      <div key={entry.id} className="flex items-center justify-between p-3 border border-[#F38D1C]/20 rounded-lg hover:bg-[#FEF6ED]/50 transition-colors">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className="w-10 h-10 rounded-full bg-[#035688]/10 flex items-center justify-center font-bold text-[#035688] flex-shrink-0">
                            {entry.rank}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-[#270A01] truncate">{entry.name}</p>
                            <p className="text-sm text-[#C04208]">{entry.conversions} sales</p>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="font-bold text-[#F38D1C]">ZMW {(entry.earnings / 1000).toFixed(1)}K</p>
                          {idx < 3 && <span className="text-xl">🏆</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
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
                onClick={() => setActiveSection(item.id)}
                className={`flex flex-col items-center justify-center gap-1 touch-target-large transition-colors ${
                  activeSection === item.id 
                    ? 'text-[#035688] bg-[#FEF6ED]' 
                    : 'text-[#C04208] hover:bg-[#FEF6ED]'
                }`}
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

export default AffiliateDashboard;

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useNavigate, useLocation } from "react-router-dom";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { 
  TrendingUp, 
  Package, 
  Users, 
  DollarSign, 
  Plus,
  AlertTriangle,
  MessageSquare,
  BarChart3
} from "lucide-react";

const MSMEDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const navigateOrScroll = (path: string, id?: string) => {
    const [p, hash] = path.split('#');
    // if already on the same base path, dispatch custom scroll event
    if (location.pathname === p) {
      // update hash without navigation so layout/listeners see it
      if (hash) {
        history.replaceState(null, '', `${p}#${hash}`);
      }
      window.dispatchEvent(new CustomEvent('ntheemba:scroll-to', { detail: { id: id || hash } }));
      return;
    }
    navigate(path);
  };

  const scrollToQuickAdd = () => {
    const el = document.getElementById("quick-add-target");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      // give a brief focus for accessibility when available
      const elm = el as HTMLElement;
      if (typeof elm.focus === "function") {
        // focus without scrolling again
        elm.focus();
      }
      return;
    }
    // fallback: navigate to products page with hash
    navigate('/msme/products#quick-add-target');
  };
  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4 max-w-7xl mx-auto">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Welcome back, Rajesh!</h1>
          <p className="text-muted-foreground text-sm sm:text-base">Here's what's happening with your business today</p>
        </div>
        <Button
          className="w-full sm:w-auto motion-safe:animate-pulse hover:motion-safe:animate-none"
          onClick={scrollToQuickAdd}
        >
          <Plus className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
          Add Product
        </Button>
      </div>

      {/* Quick Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium">Today's Sales</CardTitle>
            <DollarSign className="h-3 w-3 sm:h-4 sm:w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold">ZMW 12,340</div>
            <p className="text-xs text-muted-foreground">
              <span className="text-green-600">+15.2%</span> from yesterday
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium">New Messages</CardTitle>
            <MessageSquare className="h-3 w-3 sm:h-4 sm:w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold">5</div>
            <p className="text-xs text-muted-foreground">
              3 customer inquiries, 2 orders
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium">Low Stock Items</CardTitle>
            <AlertTriangle className="h-3 w-3 sm:h-4 sm:w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold text-orange-600">3</div>
            <p className="text-xs text-muted-foreground">
              Need immediate restocking
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium">Active Campaigns</CardTitle>
            <BarChart3 className="h-3 w-3 sm:h-4 sm:w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl sm:text-2xl font-bold">2</div>
            <p className="text-xs text-muted-foreground">
              1 seasonal, 1 product launch
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Business Health Meter */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="flex items-center text-lg sm:text-xl">
              <TrendingUp className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-primary" />
              Business Health Meter
            </CardTitle>
            <CardDescription className="text-sm">
              Overall performance indicator
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 sm:space-y-4">
            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-bold text-green-600 mb-2">87%</div>
              <Badge variant="secondary" className="bg-green-100 text-green-800 text-xs sm:text-sm">
                Excellent Performance
              </Badge>
            </div>
            
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs sm:text-sm mb-1">
                  <span>Sales Growth</span>
                  <span>92%</span>
                </div>
                <Progress value={92} className="h-2" />
              </div>
              
              <div>
                <div className="flex justify-between text-xs sm:text-sm mb-1">
                  <span>Customer Satisfaction</span>
                  <span>89%</span>
                </div>
                <Progress value={89} className="h-2" />
              </div>
              
              <div>
                <div className="flex justify-between text-xs sm:text-sm mb-1">
                  <span>Inventory Management</span>
                  <span>78%</span>
                </div>
                <Progress value={78} className="h-2" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Weekly Sales Graph */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Weekly Sales Overview</CardTitle>
            <CardDescription className="text-sm">
              Sales performance over the last 7 days
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 sm:space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xl sm:text-2xl font-bold">ZMW 85,420</span>
                <Badge className="bg-green-100 text-green-800 text-xs sm:text-sm">+12.5%</Badge>
              </div>
              
              {/* Simple bar chart representation */}
              <div className="space-y-2">
                {[
                  { day: 'Mon', amount: 15420, percentage: 70 },
                  { day: 'Tue', amount: 12340, percentage: 55 },
                  { day: 'Wed', amount: 18200, percentage: 85 },
                  { day: 'Thu', amount: 9800, percentage: 45 },
                  { day: 'Fri', amount: 16750, percentage: 75 },
                  { day: 'Sat', amount: 8910, percentage: 40 },
                  { day: 'Sun', amount: 4000, percentage: 18 },
                ].map((item) => (
                  <div key={item.day} className="flex items-center space-x-2 sm:space-x-3">
                    <span className="w-6 sm:w-8 text-xs sm:text-sm">{item.day}</span>
                    <div className="flex-1 bg-muted rounded-full h-2">
                      <div 
                        className="bg-primary h-2 rounded-full transition-all"
                        style={{ width: `${item.percentage}%` }}
                      />
                    </div>
                    <span className="text-xs sm:text-sm w-12 sm:w-16 text-right">ZMW {item.amount.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader>
          <CardTitle className="text-lg sm:text-xl">Quick Actions</CardTitle>
          <CardDescription className="text-sm">
            Common tasks to keep your business running smoothly
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
            <Button
              variant="outline"
              onClick={() => navigateOrScroll('/msme/products#quick-add-target')}
              className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 hover:shadow-sm transition-all"
            >
              <Package className="w-4 h-4 sm:w-6 sm:h-6" />
              <span className="text-xs sm:text-sm">Add Product</span>
            </Button>

            <Button
              variant="outline"
              onClick={() => navigateOrScroll('/msme/insights#total-orders')}
              className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 hover:shadow-sm transition-all"
            >
              <Users className="w-4 h-4 sm:w-6 sm:h-6" />
              <span className="text-xs sm:text-sm">View Orders</span>
            </Button>

            <Button
              variant="outline"
              onClick={() => navigateOrScroll('/msme/branding#connection')}
              className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 hover:shadow-sm transition-all"
            >
              <MessageSquare className="w-4 h-4 sm:w-6 sm:h-6" />
              <span className="text-xs sm:text-sm">Messages</span>
            </Button>

            <Button
              variant="outline"
              onClick={() => navigateOrScroll('/msme/insights#sales-performance')}
              className="h-16 sm:h-20 flex flex-col space-y-1 sm:space-y-2 hover:shadow-sm transition-all"
            >
              <BarChart3 className="w-4 h-4 sm:w-6 sm:h-6" />
              <span className="text-xs sm:text-sm">Analytics</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MSMEDashboard;
import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  TrendingUp, 
  BarChart3, 
  Users, 
  Package,
  Calendar,
  Download,
  Filter,
  ArrowUp,
  ArrowDown
} from "lucide-react";

const MSMEInsights = () => {
  const [chartType, setChartType] = useState<'line' | 'bar'>('line');
  const [timeRange, setTimeRange] = useState('7d');

  const salesData = [
    { period: 'Mon', sales: 15420, orders: 23 },
    { period: 'Tue', sales: 12340, orders: 18 },
    { period: 'Wed', sales: 18200, orders: 31 },
    { period: 'Thu', sales: 9800, orders: 15 },
    { period: 'Fri', sales: 16750, orders: 28 },
    { period: 'Sat', sales: 8910, orders: 12 },
    { period: 'Sun', sales: 4000, orders: 6 },
  ];

  const bestSellers = [
    { name: "Handwoven Cotton Saree", sales: 45, revenue: "ZMW1,12,500" },
    { name: "Organic Turmeric Powder", sales: 89, revenue: "ZMW13,350" },
    { name: "Bamboo Water Bottle", sales: 34, revenue: "ZMW15,300" },
    { name: "Leather Wallet", sales: 28, revenue: "ZMW22,400" },
    { name: "Herbal Face Cream", sales: 52, revenue: "ZMW16,640" },
  ];

  const maxSales = Math.max(...salesData.map(d => d.sales));

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const id = window.location.hash.replace('#', '');
      const el = document.getElementById(id);
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
        (el as HTMLElement).focus?.();
      }
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold">Sales & Insights</h1>
          <p className="text-muted-foreground">Analyze your business performance and trends</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Filter className="w-4 h-4 mr-2" />
            Filter
          </Button>
          <Button variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              Total Revenue
              <TrendingUp className="h-4 w-4 text-green-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">ZMW2,45,680</div>
            <div className="flex items-center text-sm">
              <ArrowUp className="w-4 h-4 text-green-600 mr-1" />
              <span className="text-green-600">+15.2%</span>
              <span className="text-muted-foreground ml-1">vs last month</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              Total Orders
              <Package className="h-4 w-4 text-blue-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">1,247</div>
            <div className="flex items-center text-sm">
              <ArrowUp className="w-4 h-4 text-green-600 mr-1" />
              <span className="text-green-600">+8.7%</span>
              <span className="text-muted-foreground ml-1">vs last month</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              Avg Order Value
              <BarChart3 className="h-4 w-4 text-purple-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">ZMW1,970</div>
            <div className="flex items-center text-sm">
              <ArrowDown className="w-4 h-4 text-red-600 mr-1" />
              <span className="text-red-600">-2.1%</span>
              <span className="text-muted-foreground ml-1">vs last month</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              New Customers
              <Users className="h-4 w-4 text-orange-600" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">348</div>
            <div className="flex items-center text-sm">
              <ArrowUp className="w-4 h-4 text-green-600 mr-1" />
              <span className="text-green-600">+22.5%</span>
              <span className="text-muted-foreground ml-1">vs last month</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales Chart */}
        <Card>
      <CardHeader id="sales-performance">
        <div className="flex items-center justify-between">
              <div>
                <CardTitle>Sales Performance</CardTitle>
                <CardDescription>Daily sales over the selected period</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button 
                  variant={chartType === 'line' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setChartType('line')}
                >
                  Line
                </Button>
                <Button 
                  variant={chartType === 'bar' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setChartType('bar')}
                >
                  Bar
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Last 7 days</span>
                <Badge variant="secondary">ZMW85,420 total</Badge>
              </div>
              
              {/* Simple chart representation */}
              <div className="space-y-3">
                {salesData.map((item, index) => (
                  <div key={item.period} className="flex items-center space-x-3">
                    <span className="w-8 text-sm text-muted-foreground">{item.period}</span>
                    <div className="flex-1 bg-muted rounded-full h-6 relative">
                      <div 
                        className="bg-primary h-6 rounded-full transition-all flex items-center justify-end pr-2"
                        style={{ width: `${(item.sales / maxSales) * 100}%` }}
                      >
                        <span className="text-xs text-primary-foreground font-medium">
                          ZMW{item.sales.toLocaleString()}
                        </span>
                      </div>
                    </div>
                    <span className="text-sm w-12 text-right">{item.orders}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Best Sellers */}
  <Card id="total-orders">
          <CardHeader>
            <CardTitle>Best Selling Products</CardTitle>
            <CardDescription>Top performing products this month</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {bestSellers.map((product, index) => (
                <div key={product.name} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </div>
                    <div>
                      <div className="font-medium text-sm">{product.name}</div>
                      <div className="text-xs text-muted-foreground">{product.sales} units sold</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium">{product.revenue}</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Customer Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Customer Insights</CardTitle>
            <CardDescription>Understanding your customer base</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>Repeat Customers</span>
                  <span className="font-medium">68%</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div className="bg-green-500 h-2 rounded-full" style={{ width: '68%' }}></div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>New Customers</span>
                  <span className="font-medium">32%</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div className="bg-blue-500 h-2 rounded-full" style={{ width: '32%' }}></div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">4.8</div>
                  <div className="text-sm text-muted-foreground">Avg Rating</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">2.3</div>
                  <div className="text-sm text-muted-foreground">Orders/Customer</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Time-based Analytics</CardTitle>
            <CardDescription>When your customers are most active</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-3">Peak Hours</h4>
                <div className="space-y-2">
                  {[
                    { time: "10:00 - 11:00 AM", percentage: 85 },
                    { time: "2:00 - 3:00 PM", percentage: 72 },
                    { time: "7:00 - 8:00 PM", percentage: 68 },
                    { time: "11:00 - 12:00 PM", percentage: 54 },
                  ].map((slot) => (
                    <div key={slot.time} className="flex items-center space-x-3">
                      <span className="text-sm w-24">{slot.time}</span>
                      <div className="flex-1 bg-muted rounded-full h-2">
                        <div 
                          className="bg-primary h-2 rounded-full" 
                          style={{ width: `${slot.percentage}%` }}
                        ></div>
                      </div>
                      <span className="text-sm w-8">{slot.percentage}%</span>
                    </div>
                  ))}
                </div>
              </div>
              
              <div>
                <h4 className="font-medium mb-3">Best Days</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="flex justify-between">
                    <span>Monday</span>
                    <Badge variant="secondary">High</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Friday</span>
                    <Badge variant="secondary">High</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Saturday</span>
                    <Badge className="bg-green-100 text-green-800">Peak</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Sunday</span>
                    <Badge variant="outline">Low</Badge>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MSMEInsights;
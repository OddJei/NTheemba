import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import API from "@/lib/api";
import {
  TrendingUp, Package, DollarSign, Plus, AlertTriangle,
  MessageSquare, BarChart3, ArrowLeft, LayoutDashboard,
  ShoppingBag, ClipboardList, X, Check, Loader2, Menu
} from "lucide-react";

interface MSMEStats {
  todaysSales: number;
  newMessages: number;
  lowStockItems: number;
  activeCampaigns: number;
  businessHealth: number;
  weeklySales: number;
}

interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  stock: number;
  category: string;
  imageUrl?: string;
  variants?: { name: string; options: string[] }[];
}

interface Order {
  id: string;
  orderId: string;
  customerName: string;
  product: string;
  amount: number;
  status: 'pending' | 'confirmed' | 'delivered' | 'denied';
  date: string;
  affiliateName?: string;
}

const MSMEDashboard = () => {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState<'dashboard' | 'inventory' | 'orders'>('dashboard');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [stats, setStats] = useState<MSMEStats>({
    todaysSales: 0,
    newMessages: 0,
    lowStockItems: 0,
    activeCampaigns: 0,
    businessHealth: 0,
    weeklySales: 0
  });
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [, setLoading] = useState(true);
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: '',
    description: '',
    price: '',
    stock: '',
    category: '',
    image: null as File | null,
    variants: [] as { name: string; options: string }[]
  });

  const [variantDraft, setVariantDraft] = useState({ name: '', options: '' });

  useEffect(() => {
    loadStats();
    loadProducts();
    loadOrders();
  }, []);

  const loadStats = async () => {
    try {
      const data = await API('/msme/stats');
      setStats({
        todaysSales: data.todaysSales || 12340,
        newMessages: data.newMessages || 5,
        lowStockItems: data.lowStockItems || 3,
        activeCampaigns: data.activeCampaigns || 2,
        businessHealth: data.businessHealth || 87,
        weeklySales: data.weeklySales || 85420
      });
    } catch (error) {
      console.error('Failed to load stats:', error);
      // Use mock data on error
      setStats({
        todaysSales: 12340,
        newMessages: 5,
        lowStockItems: 3,
        activeCampaigns: 2,
        businessHealth: 87,
        weeklySales: 85420
      });
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async () => {
    try {
      const data = await API('/msme/products');
      setProducts(data);
    } catch (error) {
      // Mock products data
      setProducts([
        { id: '1', name: 'Handmade Soap', description: 'Natural organic soap', price: 25, stock: 150, category: 'Beauty', variants: [{ name: 'Size', options: ['Small','Medium','Large'] }] },
        { id: '2', name: 'Coffee Beans 1kg', description: 'Premium arabica', price: 120, stock: 75, category: 'Food', variants: [{ name: 'Grind', options: ['Whole','Fine','Coarse'] }] },
        { id: '3', name: 'Leather Wallet', description: 'Handcrafted wallet', price: 180, stock: 8, category: 'Fashion', variants: [{ name: 'Color', options: ['Tan','Black'] }] },
        { id: '4', name: 'Wooden Table', description: 'Solid oak table', price: 2500, stock: 5, category: 'Furniture', variants: [] }
      ]);
    }
  };

  const loadOrders = async () => {
    try {
      const data = await API('/msme/orders');
      setOrders(data);
    } catch (error) {
      // Mock orders data
      setOrders([
        { id: '1', orderId: 'ORD-001', customerName: 'Priya Sharma', product: 'Handmade Soap', amount: 75, status: 'pending', date: '2024-01-20', affiliateName: 'James Banda' },
        { id: '2', orderId: 'ORD-002', customerName: 'Michael Chen', product: 'Coffee Beans 1kg', amount: 240, status: 'pending', date: '2024-01-20' },
        { id: '3', orderId: 'ORD-003', customerName: 'Sarah Mwale', product: 'Leather Wallet', amount: 180, status: 'confirmed', date: '2024-01-19', affiliateName: 'Grace Phiri' },
        { id: '4', orderId: 'ORD-004', customerName: 'John Phiri', product: 'Wooden Table', amount: 2500, status: 'delivered', date: '2024-01-18' }
      ]);
    }
  };

  const handleAddProduct = async () => {
    if (!newProduct.name || !newProduct.price || !newProduct.stock) {
      alert('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('name', newProduct.name);
      formData.append('description', newProduct.description);
      formData.append('price', newProduct.price);
      formData.append('stock', newProduct.stock);
      formData.append('category', newProduct.category);
      if (newProduct.image) {
        formData.append('image', newProduct.image);
      }

      // attach variants if present
      if (newProduct.variants && newProduct.variants.length > 0) {
        // transform "options" comma string into array per variant
        const parsed = newProduct.variants.map(v => ({ name: v.name, options: v.options.split(',').map(s => s.trim()).filter(Boolean) }));
        formData.append('variants', JSON.stringify(parsed));
      }

      await API('/msme/products', {
        method: 'POST',
        body: formData
      });

      alert('Product added successfully!');
      setIsAddProductOpen(false);
      setNewProduct({ name: '', description: '', price: '', stock: '', category: '', image: null, variants: [] });
      loadProducts();
    } catch (error) {
      alert('Failed to add product. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOrderAction = async (orderId: string, action: 'confirm' | 'deny') => {
    try {
      await API(`/msme/orders/${orderId}/${action}`, {
        method: 'PUT'
      });
      alert(`Order ${action === 'confirm' ? 'confirmed' : 'denied'} successfully!`);
      loadOrders();
    } catch (error) {
      alert(`Failed to ${action} order. Please try again.`);
    }
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setNewProduct({ ...newProduct, image: e.target.files[0] });
    }
  };

  const weeklyData = [
    { day: 'Mon', amount: 15420, percentage: 70 },
    { day: 'Tue', amount: 12340, percentage: 55 },
    { day: 'Wed', amount: 18200, percentage: 85 },
    { day: 'Thu', amount: 9800, percentage: 45 },
    { day: 'Fri', amount: 16750, percentage: 75 },
    { day: 'Sat', amount: 8910, percentage: 40 },
    { day: 'Sun', amount: 4000, percentage: 18 },
  ];

  const navItems = [
    { id: 'dashboard' as const, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'inventory' as const, label: 'Inventory', icon: ShoppingBag },
    { id: 'orders' as const, label: 'Orders', icon: ClipboardList },
  ];

  return (
    <div className="min-h-screen bg-[#FEF6ED] flex flex-col md:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:flex-col w-64 h-screen sticky top-0 border-r bg-[#035688] p-4 flex-shrink-0">
        <div className="flex items-center gap-2 mb-6">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="hover:bg-[#0A3F5F] touch-target">
            <ArrowLeft className="w-4 h-4 text-white" />
          </Button>
          <div>
            <h2 className="font-bold text-white">NTheemba</h2>
            <p className="text-xs text-[#F38D1C]">MSME Portal</p>
          </div>
        </div>

        <div className="space-y-2">
          {navItems.map((item) => (
            <Button
              key={item.id}
              className={`w-full justify-start text-white touch-target ${
                activeSection === item.id ? 'bg-[#F38D1C] hover:bg-[#E67E10]' : 'hover:bg-[#0A3F5F]'
              }`}
              onClick={() => setActiveSection(item.id)}
            >
              <item.icon className="w-4 h-4 mr-2" />
              {item.label}
            </Button>
          ))}
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
            <div>
              <h2 className="font-bold text-base text-white">NTheemba</h2>
              <p className="text-xs text-[#F38D1C]">MSME</p>
            </div>
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
              {navItems.map((item) => (
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
                  <item.icon className="w-5 h-5 mr-3" />
                  <span className="text-base">{item.label}</span>
                </Button>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="w-full">
          {activeSection === 'dashboard' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-[#270A01]">Dashboard</h1>
                <p className="text-sm text-[#C04208]">What's happening with your business today</p>
              </div>

            {/* Quick Stats Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="border-[#F38D1C]/20">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-[#270A01]">Today's Sales</CardTitle>
                  <DollarSign className="h-4 w-4 text-[#035688]" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[#035688]">ZMW {stats.todaysSales.toLocaleString()}</div>
                  <p className="text-xs text-[#C04208]">
                    <span className="text-[#F38D1C] font-semibold">+15.2%</span> from yesterday
                  </p>
                </CardContent>
              </Card>

              <Card className="border-[#F38D1C]/20">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-[#270A01]">New Messages</CardTitle>
                  <MessageSquare className="h-4 w-4 text-[#F38D1C]" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[#F38D1C]">{stats.newMessages}</div>
                  <p className="text-xs text-[#C04208]">3 customer inquiries, 2 orders</p>
                </CardContent>
              </Card>

              <Card className="border-[#F38D1C]/20">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-[#270A01]">Low Stock Items</CardTitle>
                  <AlertTriangle className="h-4 w-4 text-[#C04208]" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[#C04208]">{stats.lowStockItems}</div>
                  <p className="text-xs text-[#C04208]">Need immediate restocking</p>
                </CardContent>
              </Card>

              <Card className="border-[#F38D1C]/20">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-[#270A01]">Active Campaigns</CardTitle>
                  <BarChart3 className="h-4 w-4 text-[#035688]" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[#035688]">{stats.activeCampaigns}</div>
                  <p className="text-xs text-[#C04208]">1 seasonal, 1 product launch</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Business Health Meter */}
              <Card className="border-[#F38D1C]/20">
                <CardHeader>
                  <CardTitle className="flex items-center text-[#270A01]">
                    <TrendingUp className="w-5 h-5 mr-2 text-[#035688]" />
                    Business Health Meter
                  </CardTitle>
                  <CardDescription className="text-[#C04208]">Overall performance indicator</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-[#F38D1C] mb-2">{stats.businessHealth}%</div>
                    <Badge className="bg-[#F38D1C]/20 text-[#C04208] border-[#F38D1C]">
                      Excellent Performance
                    </Badge>
                  </div>
                  
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-sm mb-1 text-[#270A01]">
                        <span>Sales Growth</span>
                        <span>92%</span>
                      </div>
                      <Progress value={92} className="h-2 bg-[#F38D1C]/20" />
                    </div>
                    
                    <div>
                      <div className="flex justify-between text-sm mb-1 text-[#270A01]">
                        <span>Customer Satisfaction</span>
                        <span>89%</span>
                      </div>
                      <Progress value={89} className="h-2 bg-[#F38D1C]/20" />
                    </div>
                    
                    <div>
                      <div className="flex justify-between text-sm mb-1 text-[#270A01]">
                        <span>Inventory Management</span>
                        <span>78%</span>
                      </div>
                      <Progress value={78} className="h-2 bg-[#F38D1C]/20" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Weekly Sales Graph */}
              <Card className="border-[#F38D1C]/20">
                <CardHeader>
                  <CardTitle className="text-[#270A01]">Weekly Sales Overview</CardTitle>
                  <CardDescription className="text-[#C04208]">Sales performance over the last 7 days</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-2xl font-bold text-[#035688]">ZMW {stats.weeklySales.toLocaleString()}</span>
                      <Badge className="bg-[#F38D1C]/20 text-[#C04208]">+12.5%</Badge>
                    </div>
                    
                    <div className="space-y-2">
                      {weeklyData.map((item) => (
                        <div key={item.day} className="flex items-center space-x-3">
                          <span className="w-8 text-sm text-[#270A01] font-medium">{item.day}</span>
                          <div className="flex-1 bg-[#FEF6ED] rounded-full h-2">
                            <div 
                              className="bg-[#035688] h-2 rounded-full transition-all"
                              style={{ width: `${item.percentage}%` }}
                            />
                          </div>
                          <span className="text-sm w-16 text-right text-[#035688] font-semibold">ZMW {item.amount.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {activeSection === 'inventory' && (
          <div className="space-y-6 p-6">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-2xl font-bold text-[#270A01]">Inventory Management</h1>
                <p className="text-sm text-[#C04208]">Manage your products and stock levels</p>
              </div>
              <Button onClick={() => setIsAddProductOpen(true)} className="bg-[#035688] hover:bg-[#0A3F5F] text-white">
                <Plus className="w-4 h-4 mr-2" />
                Add Product
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {products.map((product) => (
                <Card key={product.id} className="hover:shadow-md transition-shadow border-[#F38D1C]/20">
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-lg text-[#270A01]">{product.name}</CardTitle>
                        <p className="text-sm text-[#C04208] mt-1">{product.category}</p>
                      </div>
                      <Badge className={product.stock < 10 ? 'bg-[#C04208]' : 'bg-[#F38D1C]/20 text-[#035688]'}>
                        Stock: {product.stock}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-[#C04208] mb-3">{product.description}</p>
                    <div className="flex justify-between items-center">
                      <span className="text-2xl font-bold text-[#035688]">ZMW {product.price}</span>
                      <Button variant="outline" size="sm" className="border-[#035688]">
                        Edit
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Add Product Dialog */}
            <Dialog open={isAddProductOpen} onOpenChange={setIsAddProductOpen}>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle>Add New Product</DialogTitle>
                  <DialogDescription>
                    Fill in the details to add a new product to your inventory
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="name">Product Name *</Label>
                    <Input
                      id="name"
                      placeholder="e.g., Handmade Soap"
                      value={newProduct.name}
                      onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                    />
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      placeholder="Product description..."
                      value={newProduct.description}
                      onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="price">Price (ZMW) *</Label>
                      <Input
                        id="price"
                        type="number"
                        placeholder="25"
                        value={newProduct.price}
                        onChange={(e) => setNewProduct({ ...newProduct, price: e.target.value })}
                      />
                    </div>
                    
                    <div className="grid gap-2">
                      <Label htmlFor="stock">Stock Quantity *</Label>
                      <Input
                        id="stock"
                        type="number"
                        placeholder="100"
                        value={newProduct.stock}
                        onChange={(e) => setNewProduct({ ...newProduct, stock: e.target.value })}
                      />
                    </div>
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="category">Category</Label>
                    <select
                      id="category"
                      value={newProduct.category}
                      onChange={(e) => setNewProduct({ ...newProduct, category: e.target.value })}
                      className="w-full rounded-md border px-3 py-2"
                    >
                      <option value="">Select a category</option>
                      {[
                        'Beauty',
                        'Food',
                        'Fashion',
                        'Furniture',
                        'Electronics',
                        'Home',
                      ].map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                      {/* also include any dynamic categories from existing products */}
                      {Array.from(new Set(products.map(p => p.category))).map((c) => (
                        c && <option key={`dyn-${c}`} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  {/* Variants */}
                  <div className="grid gap-2">
                    <Label>Variants (optional)</Label>
                    <div className="flex gap-2">
                      <Input
                        placeholder="Variant name (e.g., Size)"
                        value={variantDraft.name}
                        onChange={(e) => setVariantDraft({ ...variantDraft, name: e.target.value })}
                      />
                      <Input
                        placeholder="Options (comma separated, e.g., S,M,L)"
                        value={variantDraft.options}
                        onChange={(e) => setVariantDraft({ ...variantDraft, options: e.target.value })}
                      />
                      <Button
                        onClick={() => {
                          if (!variantDraft.name.trim() || !variantDraft.options.trim()) return;
                          setNewProduct({ ...newProduct, variants: [...newProduct.variants, { name: variantDraft.name.trim(), options: variantDraft.options.trim() }] });
                          setVariantDraft({ name: '', options: '' });
                        }}
                      >
                        Add
                      </Button>
                    </div>

                    <div className="flex flex-col gap-2">
                      {newProduct.variants.map((v, idx) => (
                        <div key={`v-${idx}`} className="flex items-center justify-between gap-2 p-2 border rounded">
                          <div>
                            <div className="font-medium text-[#270A01]">{v.name}</div>
                            <div className="text-sm text-[#C04208]">{v.options}</div>
                          </div>
                          <div>
                            <Button size="sm" variant="destructive" onClick={() => setNewProduct({ ...newProduct, variants: newProduct.variants.filter((_, i) => i !== idx) })}>Remove</Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="image">Product Image</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="image"
                        type="file"
                        accept="image/*"
                        onChange={handleImageChange}
                        className="cursor-pointer"
                      />
                      {newProduct.image && (
                        <Badge variant="secondary" className="whitespace-nowrap">
                          {newProduct.image.name}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsAddProductOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleAddProduct} disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                    Add Product
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}

        {activeSection === 'orders' && (
          <div className="space-y-6 p-6">
            <div>
              <h1 className="text-2xl font-bold text-[#270A01]">Orders Management</h1>
              <p className="text-sm text-[#C04208]">Manage incoming orders and deliveries</p>
            </div>

            <div className="grid gap-4">
              {orders.filter((o: any) => o.status === 'pending' || o.status === 'confirmed').map((order: any) => (
                <Card key={order.id} className="border-[#F38D1C]/20">
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-lg text-[#270A01]">{order.orderId}</h3>
                          <Badge className={
                            order.status === 'pending' ? 'bg-[#F38D1C]' :
                            order.status === 'confirmed' ? 'bg-[#035688]' :
                            order.status === 'delivered' ? 'bg-[#F38D1C]/20 text-[#035688]' : 'bg-[#C04208]'
                          }>
                            {order.status.toUpperCase()}
                          </Badge>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="text-[#C04208]">Customer</p>
                            <p className="font-medium text-[#270A01]">{order.customerName}</p>
                          </div>
                          <div>
                            <p className="text-[#C04208]">Product</p>
                            <p className="font-medium text-[#270A01]">{order.product}</p>
                          </div>
                          <div>
                            <p className="text-[#C04208]">Amount</p>
                            <p className="font-bold text-[#F38D1C]">ZMW {order.amount.toLocaleString()}</p>
                          </div>
                          <div>
                            <p className="text-[#C04208]">Date</p>
                            <p className="font-medium text-[#270A01]">{order.date}</p>
                          </div>
                          {order.affiliateName && (
                            <div className="col-span-2">
                              <p className="text-[#C04208]">Referred by Affiliate</p>
                              <p className="font-medium text-[#270A01]">{order.affiliateName}</p>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex gap-2 ml-4">
                        {order.status === 'pending' && (
                          <>
                            <Button
                              size="sm"
                              variant="default"
                              onClick={() => handleOrderAction(order.id, 'confirm')}
                              className="bg-[#035688] hover:bg-[#0A3F5F]"
                            >
                              <Check className="w-4 h-4 mr-1" />
                              Confirm
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleOrderAction(order.id, 'deny')}
                            >
                              <X className="w-4 h-4 mr-1" />
                              Deny
                            </Button>
                          </>
                        )}
                        {order.status === 'confirmed' && (
                          <Button
                            size="sm"
                            variant="default"
                            onClick={() => handleOrderAction(order.id, 'confirm')}
                          >
                            <Package className="w-4 h-4 mr-1" />
                            Confirm Delivery
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              
              {orders.filter((o: any) => o.status === 'pending' || o.status === 'confirmed').length === 0 && (
                <Card>
                  <CardContent className="py-12 text-center">
                    <ClipboardList className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                    <p className="text-muted-foreground">No pending orders</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        )}
        </div>
      </main>
    </div>
  );
};

export default MSMEDashboard;

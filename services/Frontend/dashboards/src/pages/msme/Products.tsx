import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import API from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { 
  Plus, 
  Search, 
  Filter, 
  Upload,
  Edit,
  Trash2,
  Eye,
  Package
} from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const MSMEProducts = () => {
  const [searchTerm, setSearchTerm] = useState("");

  const products = [
    {
      id: 1,
      name: "Handwoven Cotton Saree",
      category: "Textiles",
      price: "ZMW 2,500",
      stock: 15,
      status: "Active",
      image: "/placeholder.svg"
    },
    {
      id: 2,
      name: "Organic Turmeric Powder",
      category: "Spices",
      price: "ZMW 150",
      stock: 3,
      status: "Low Stock",
      image: "/placeholder.svg"
    },
    {
      id: 3,
      name: "Bamboo Water Bottle",
      category: "Eco Products",
      price: "ZMW 450",
      stock: 25,
      status: "Active",
      image: "/placeholder.svg"
    },
    {
      id: 4,
      name: "Leather Wallet",
      category: "Accessories",
      price: "ZMW 800",
      stock: 0,
      status: "Out of Stock",
      image: "/placeholder.svg"
    },
    {
      id: 5,
      name: "Herbal Face Cream",
      category: "Cosmetics",
      price: "ZMW 320",
      stock: 40,
      status: "Active",
      image: "/placeholder.svg"
    }
  ];

  const getStatusBadge = (status: string, stock: number) => {
    if (status === "Out of Stock" || stock === 0) {
      return <Badge variant="destructive">Out of Stock</Badge>;
    }
    if (status === "Low Stock" || stock <= 5) {
      return <Badge className="bg-orange-100 text-orange-800">Low Stock</Badge>;
    }
    return <Badge className="bg-green-100 text-green-800">Active</Badge>;
  };

  // Quick add state
  const [quickType, setQuickType] = useState<'product' | 'service'>('product');
  const [quickName, setQuickName] = useState('');
  const [quickPrice, setQuickPrice] = useState('');
  const [quickStock, setQuickStock] = useState('');

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const addItemMutation = useMutation(
    (payload: unknown) => API('/msme/products', { method: 'POST', body: JSON.stringify(payload) }),
    {
      onSuccess: (data: unknown) => {
        queryClient.invalidateQueries(['msme', 'products']);
        toast({ title: 'Added', description: `${quickType === 'product' ? 'Product' : 'Service'} added` });
        setQuickName(''); setQuickPrice(''); setQuickStock(''); setQuickType('product');
      },
      onError: (err: unknown) => {
        const e = err as { data?: any } | undefined;
        toast({ title: 'Error', description: e?.data?.message || 'Could not add item', variant: 'destructive' });
      }
    }
  );

  const handleQuickAdd = () => {
    if (!quickName.trim()) return toast({ title: 'Validation', description: 'Please enter a name', variant: 'destructive' });
    if (quickType === 'product' && !quickStock.trim()) return toast({ title: 'Validation', description: 'Please enter stock for a product', variant: 'destructive' });

    const payload = {
      type: quickType,
      name: quickName.trim(),
      price: quickPrice.trim() || '0',
      stock: quickType === 'product' ? Number(quickStock || 0) : undefined
    };

    addItemMutation.mutate(payload);
  };

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const id = window.location.hash.replace('#', '');
      const el = document.getElementById(id);
      if (el) {
        // small timeout to allow layout to settle
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
        // focus for a11y
        (el as HTMLElement).focus?.();
      }
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold">Products & Services</h1>
          <p className="text-muted-foreground">Manage your product catalog and inventory</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Upload className="w-4 h-4 mr-2" />
            Bulk Upload
          </Button>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Add Product
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Products</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">127</div>
            <p className="text-xs text-muted-foreground">+5 this month</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Products</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">98</div>
            <p className="text-xs text-muted-foreground">77% of total</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Low Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">12</div>
            <p className="text-xs text-muted-foreground">Need restocking</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Out of Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">17</div>
            <p className="text-xs text-muted-foreground">Immediate attention</p>
          </CardContent>
        </Card>
      </div>

    {/* Search and Filters */}
  <Card id="quick-add-target" tabIndex={-1}>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search products..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button variant="outline">
              <Filter className="w-4 h-4 mr-2" />
              Filters
            </Button>
          </div>
        </CardHeader>

        {/* Products Table */}
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Stock</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((product) => (
                <TableRow key={product.id}>
                  <TableCell>
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-muted rounded-md flex items-center justify-center">
                        <Package className="w-5 h-5 text-muted-foreground" />
                      </div>
                      <div>
                        <div className="font-medium">{product.name}</div>
                        <div className="text-sm text-muted-foreground">ID: {product.id}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{product.category}</TableCell>
                  <TableCell className="font-medium">{product.price}</TableCell>
                  <TableCell>
                    <span className={product.stock <= 5 ? "text-orange-600" : ""}>{product.stock}</span>
                  </TableCell>
                  <TableCell>
                    {getStatusBadge(product.status, product.stock)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end space-x-2">
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Quick Add Product */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Add Product / Service</CardTitle>
          <CardDescription>
            Add a new product or service to your catalog quickly
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="text-xs text-muted-foreground">Type</label>
              <Select onValueChange={(v) => setQuickType(v as 'product' | 'service')} value={quickType}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Product or Service" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="product">Product</SelectItem>
                  <SelectItem value="service">Service</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-xs text-muted-foreground">Name</label>
              <Input placeholder="Name" value={quickName} onChange={(e) => setQuickName(e.target.value)} />
            </div>

            <div>
              <label className="text-xs text-muted-foreground">Price (ZMW)</label>
              <Input placeholder="Price (e.g. 120)" value={quickPrice} onChange={(e) => setQuickPrice(e.target.value)} />
            </div>

            <div>
              <label className="text-xs text-muted-foreground">Stock</label>
              <Input placeholder={quickType === 'product' ? 'Stock quantity' : 'N/A for services'} value={quickStock} onChange={(e) => setQuickStock(e.target.value)} disabled={quickType === 'service'} />
            </div>
          </div>
          <div className="flex justify-end mt-4">
            <Button onClick={handleQuickAdd}>Add {quickType === 'product' ? 'Product' : 'Service'}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MSMEProducts;
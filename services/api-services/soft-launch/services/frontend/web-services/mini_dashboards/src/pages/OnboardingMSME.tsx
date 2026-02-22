import { useState, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { msmeOnboard } from '@/lib/clients';
import { ArrowLeft, ArrowRight, CheckCircle, User, Building2, Package, TrendingUp, Plus } from "lucide-react";

type Step = 'profile' | 'business' | 'products' | 'complete';

interface ProfileData {
  fullName: string;
  email: string;
  phone: string;
  location: string;
  termsAccepted: boolean;
}

interface BusinessData {
  businessName: string;
  businessType: string;
  description: string;
  yearsInBusiness: string;
}

interface ProductData {
  name: string;
  category: string;
  price: string;
  initialStock: string;
}

const OnboardingMSME = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('profile');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [profile, setProfile] = useState<ProfileData>({
    fullName: '',
    email: '',
    phone: '',
    location: '',
    termsAccepted: false
  });

  const [business, setBusiness] = useState<BusinessData>({
    businessName: '',
    businessType: '',
    description: '',
    yearsInBusiness: ''
  });

  const [products, setProducts] = useState<ProductData[]>([
    { name: '', category: '', price: '', initialStock: '' }
  ]);

  const businessTypes = [
    'Beauty & Personal Care',
    'Food & Beverages',
    'Fashion & Accessories',
    'Home & Furniture',
    'Tech & Electronics',
    'Crafts & Artisan',
    'Agriculture',
    'Services',
    'Other'
  ];

  const productCategories = [
    'Beauty',
    'Food',
    'Fashion',
    'Furniture',
    'Tech',
    'Crafts',
    'Agriculture',
    'Other'
  ];

  const handleProfileChange = (field: keyof ProfileData, value: string | boolean) => {
    setProfile(prev => ({ ...prev, [field]: value }));
  };

  const handleBusinessChange = (field: keyof BusinessData, value: string) => {
    setBusiness(prev => ({ ...prev, [field]: value }));
  };

  const handleProductChange = (index: number, field: keyof ProductData, value: string) => {
    const newProducts = [...products];
    newProducts[index] = { ...newProducts[index], [field]: value };
    setProducts(newProducts);
  };

  const addProduct = () => {
    setProducts([...products, { name: '', category: '', price: '', initialStock: '' }]);
  };

  const removeProduct = (index: number) => {
    setProducts(products.filter((_, i) => i !== index));
  };

  const handleProfileSubmit = async () => {
    if (!profile.fullName || !profile.email || !profile.phone) {
      alert('Please fill in all required fields');
      return;
    }
    if (!profile.termsAccepted) {
      alert('Please accept the terms and conditions');
      return;
    }
    setStep('business');
  };

  const handleBusinessSubmit = async () => {
    if (!business.businessName || !business.businessType) {
      alert('Please fill in all required fields');
      return;
    }
    setStep('products');
  };

  const handleProductsSubmit = async () => {
    if (products.some(p => !p.name || !p.price || !p.initialStock)) {
      alert('Please complete all product fields');
      return;
    }

    setIsSubmitting(true);
    try {
      await msmeOnboard({ profile, business, products });
      setStep('complete');
    } catch (error) {
      alert('Failed to complete onboarding. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCompleteOnboarding = () => {
    navigate('/msme');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#FEF6ED] to-[#F38D1C]/10">
      {/* Header */}
      <header className="border-b bg-[#FEF6ED]">
        <div className="container mx-auto px-4 py-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="text-[#035688]">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <h1 className="text-2xl font-bold mt-4 text-[#270A01]">MSME Registration</h1>
          <p className="text-sm text-[#C04208]">Set up your business on NTheemba</p>
        </div>
      </header>

      {/* Progress Indicator */}
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-center gap-4 mb-8 overflow-x-auto pb-4">
          <div className={`flex flex-col items-center gap-2 min-w-fit ${step === 'profile' || step === 'business' || step === 'products' || step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
              step === 'profile' || step === 'business' || step === 'products' || step === 'complete' ? 'border-[#035688] bg-[#035688]/10' : 'border-muted'
            }`}>
              <User className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Profile</span>
          </div>

          <div className={`w-8 h-1 rounded-full ${step === 'business' || step === 'products' || step === 'complete' ? 'bg-[#035688]' : 'bg-muted'}`} />

          <div className={`flex flex-col items-center gap-2 min-w-fit ${step === 'business' || step === 'products' || step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
              step === 'business' || step === 'products' || step === 'complete' ? 'border-[#035688] bg-[#035688]/10' : 'border-muted'
            }`}>
              <Building2 className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Business</span>
          </div>

          <div className={`w-8 h-1 rounded-full ${step === 'products' || step === 'complete' ? 'bg-[#035688]' : 'bg-muted'}`} />

          <div className={`flex flex-col items-center gap-2 min-w-fit ${step === 'products' || step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
              step === 'products' || step === 'complete' ? 'border-[#035688] bg-[#035688]/10' : 'border-muted'
            }`}>
              <Package className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Products</span>
          </div>

          <div className={`w-8 h-1 rounded-full ${step === 'complete' ? 'bg-[#035688]' : 'bg-muted'}`} />

          <div className={`flex flex-col items-center gap-2 min-w-fit ${step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
              step === 'complete' ? 'border-[#035688] bg-[#035688]/10' : 'border-muted'
            }`}>
              <CheckCircle className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Complete</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="container mx-auto px-4 pb-12">
        {step === 'profile' && (
          <Card className="max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle>Owner's Profile</CardTitle>
              <CardDescription>Tell us about yourself</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4">
                <div>
                  <Label htmlFor="fullName">Full Name *</Label>
                  <Input
                    id="fullName"
                    placeholder="John Doe"
                    value={profile.fullName}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleProfileChange('fullName', e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="email">Email Address *</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="john@business.com"
                    value={profile.email}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleProfileChange('email', e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="phone">Phone Number *</Label>
                  <Input
                    id="phone"
                    placeholder="+260 123 456 789"
                    value={profile.phone}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleProfileChange('phone', e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="location">Location</Label>
                  <Input
                    id="location"
                    placeholder="Lusaka, Zambia"
                    value={profile.location}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleProfileChange('location', e.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-start space-x-3 pt-4 border-t">
                <Checkbox
                  id="terms"
                  checked={profile.termsAccepted}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleProfileChange('termsAccepted', e.target.checked)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <Label
                    htmlFor="terms"
                    className="text-sm font-normal text-gray-700 cursor-pointer"
                  >
                    I agree to the{' '}
                    <a
                      href="/terms"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline font-medium"
                    >
                      Terms and Conditions
                    </a>{' '}
                    and{' '}
                    <a
                      href="/privacy"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline font-medium"
                    >
                      Privacy Policy
                    </a>
                  </Label>
                </div>
              </div>

              <div className="flex justify-end gap-4">
                <Button variant="outline" onClick={() => navigate('/')}>
                  Cancel
                </Button>
                <Button onClick={handleProfileSubmit} className="bg-[#035688] hover:bg-[#0A3F5F] text-white">
                  Next
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 'business' && (
          <Card className="max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle>Business Details</CardTitle>
              <CardDescription>Information about your business</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4">
                <div>
                  <Label htmlFor="businessName">Business Name *</Label>
                  <Input
                    id="businessName"
                    placeholder="My Awesome Business"
                    value={business.businessName}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleBusinessChange('businessName', e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="businessType">Business Type *</Label>
                  <select
                    id="businessType"
                    title="Business Type"
                    value={business.businessType}
                    onChange={(e: ChangeEvent<HTMLSelectElement>) => handleBusinessChange('businessType', e.target.value)}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  >
                    <option value="">Select business type...</option>
                    {businessTypes.map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <Label htmlFor="yearsInBusiness">Years in Business</Label>
                  <select
                    id="yearsInBusiness"
                    title="Years in Business"
                    value={business.yearsInBusiness}
                    onChange={(e: ChangeEvent<HTMLSelectElement>) => handleBusinessChange('yearsInBusiness', e.target.value)}
                    className="w-full px-3 py-2 border rounded-md bg-background"
                  >
                    <option value="">Select...</option>
                    <option value="0-1">Less than 1 year</option>
                    <option value="1-3">1 - 3 years</option>
                    <option value="3-5">3 - 5 years</option>
                    <option value="5+">More than 5 years</option>
                  </select>
                </div>

                <div>
                  <Label htmlFor="description">Business Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Tell us about your business..."
                    value={business.description}
                    onChange={(e: ChangeEvent<HTMLTextAreaElement>) => handleBusinessChange('description', e.target.value)}
                    className="h-32"
                  />
                </div>
              </div>

              <div className="flex justify-between gap-4">
                <Button variant="outline" onClick={() => setStep('profile')}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
                <Button onClick={handleBusinessSubmit} className="bg-[#035688] hover:bg-[#0A3F5F] text-white">
                  Next
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 'products' && (
          <Card className="max-w-4xl mx-auto">
            <CardHeader>
              <CardTitle>Add Initial Products</CardTitle>
              <CardDescription>Add at least one product to get started</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {products.map((product, index) => (
                <div key={index} className="p-4 border rounded-lg space-y-4">
                  <div className="flex justify-between items-center">
                    <h4 className="font-semibold">Product {index + 1}</h4>
                    {products.length > 1 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeProduct(index)}
                      >
                        Remove
                      </Button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor={`name-${index}`}>Product Name *</Label>
                      <Input
                        id={`name-${index}`}
                        placeholder="e.g., Handmade Soap"
                        value={product.name}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => handleProductChange(index, 'name', e.target.value)}
                      />
                    </div>

                    <div>
                      <Label htmlFor={`category-${index}`}>Category</Label>
                      <select
                        id={`category-${index}`}
                        title="Product Category"
                        value={product.category}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => handleProductChange(index, 'category', e.target.value)}
                        className="w-full px-3 py-2 border rounded-md bg-background"
                      >
                        <option value="">Select category...</option>
                        {productCategories.map(cat => (
                          <option key={cat} value={cat}>{cat}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <Label htmlFor={`price-${index}`}>Price (ZMW) *</Label>
                      <Input
                        id={`price-${index}`}
                        type="number"
                        placeholder="50"
                        value={product.price}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => handleProductChange(index, 'price', e.target.value)}
                      />
                    </div>

                    <div>
                      <Label htmlFor={`stock-${index}`}>Initial Stock Quantity *</Label>
                      <Input
                        id={`stock-${index}`}
                        type="number"
                        placeholder="100"
                        value={product.initialStock}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => handleProductChange(index, 'initialStock', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ))}

              <Button variant="outline" onClick={addProduct} className="w-full">
                <Plus className="w-4 h-4 mr-2" />
                Add Another Product
              </Button>

              <div className="flex justify-between gap-4">
                <Button variant="outline" onClick={() => setStep('business')}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
                <Button onClick={handleProductsSubmit} disabled={isSubmitting} className="bg-[#035688] hover:bg-[#0A3F5F] text-white">
                  {isSubmitting ? 'Completing...' : 'Complete Registration'}
                  <CheckCircle className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 'complete' && (
          <Card className="max-w-2xl mx-auto">
            <CardContent className="py-12 text-center space-y-6">
              <div className="flex justify-center">
                <div className="w-20 h-20 rounded-full bg-[#F38D1C]/20 flex items-center justify-center">
                  <CheckCircle className="w-10 h-10 text-[#F38D1C]" />
                </div>
              </div>

              <div>
                <h2 className="text-2xl font-bold mb-2 text-[#270A01]">Welcome to NTheemba!</h2>
                <p className="text-muted-foreground">
                  Your business is now live. Start managing your inventory and orders.
                </p>
              </div>

              <div className="bg-[#F38D1C]/10 border border-[#F38D1C]/20 rounded-lg p-4 text-left">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-[#F38D1C]" />
                  Quick Start Guide
                </h3>
                <ul className="text-sm space-y-1 text-muted-foreground">
                  <li>✓ Manage your product inventory</li>
                  <li>✓ Process customer orders</li>
                  <li>✓ Connect with affiliates to boost sales</li>
                  <li>✓ Track your business metrics</li>
                  <li>✓ Upload product images</li>
                </ul>
              </div>

              <Button onClick={handleCompleteOnboarding} size="lg" className="w-full bg-[#035688] hover:bg-[#0A3F5F] text-white">
                Go to Your Dashboard
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
};

export default OnboardingMSME;

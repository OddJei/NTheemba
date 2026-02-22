import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Building2, 
  Share2, 
  Users, 
  ArrowRight,
  CheckCircle,
  AlertCircle,
  Loader2
} from "lucide-react";

type UserRole = 'msme' | 'affiliate' | 'customer' | null;
type OnboardingStep = 'role-selection' | 'form' | 'confirmation';

interface MSMEData {
  businessName: string;
  businessPhone: string;
  location: string;
  businessType: string;
  description: string;
  ownerName: string;
}

interface AffiliateData {
  fullName: string;
  whatsappNumber: string;
  cityLocation: string;
  experience: string;
  referralCode?: string;
}

interface CustomerData {
  fullName: string;
  phoneNumber: string;
  email: string;
  preferredLanguage: string;
}

const Onboarding = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<OnboardingStep>('role-selection');
  const [selectedRole, setSelectedRole] = useState<UserRole>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Form states
  const [msmeData, setMsmeData] = useState<MSMEData>({
    businessName: '',
    businessPhone: '',
    location: '',
    businessType: '',
    description: '',
    ownerName: '',
  });

  const [affiliateData, setAffiliateData] = useState<AffiliateData>({
    fullName: '',
    whatsappNumber: '',
    cityLocation: '',
    experience: '',
    referralCode: '',
  });

  const [customerData, setCustomerData] = useState<CustomerData>({
    fullName: '',
    phoneNumber: '',
    email: '',
    preferredLanguage: 'en',
  });

  // Role selection handlers
  const handleRoleSelect = (role: UserRole) => {
    setSelectedRole(role);
    setError('');
    setStep('form');
  };

  const handleBackToRoles = () => {
    setStep('role-selection');
    setSelectedRole(null);
    setError('');
  };

  // MSME form handlers
  const handleMsmeInputChange = (field: keyof MSMEData, value: string) => {
    setMsmeData(prev => ({ ...prev, [field]: value }));
  };

  const validateMsmeForm = () => {
    if (!msmeData.businessName.trim()) {
      setError('Business name is required');
      return false;
    }
    if (!msmeData.businessPhone.trim()) {
      setError('Business phone is required');
      return false;
    }
    if (!msmeData.ownerName.trim()) {
      setError('Owner name is required');
      return false;
    }
    if (!msmeData.businessType) {
      setError('Business type is required');
      return false;
    }
    return true;
  };

  const handleMsmeSubmit = async () => {
    if (!validateMsmeForm()) return;

    setLoading(true);
    setError('');
    try {
      const response = await fetch('http://127.0.0.1:8500/business', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: msmeData.businessName,
          phone: msmeData.businessPhone,
          location: msmeData.location,
          business_type: msmeData.businessType,
          description: msmeData.description,
          owner_name: msmeData.ownerName,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create business');
      }

      const result = await response.json();
      setSuccess(true);
      setStep('confirmation');
      
      // Auto-redirect after 3 seconds
      setTimeout(() => {
        navigate('/msme/dashboard');
      }, 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Affiliate form handlers
  const handleAffiliateInputChange = (field: keyof AffiliateData, value: string) => {
    setAffiliateData(prev => ({ ...prev, [field]: value }));
  };

  const validateAffiliateForm = () => {
    if (!affiliateData.fullName.trim()) {
      setError('Full name is required');
      return false;
    }
    if (!affiliateData.whatsappNumber.trim()) {
      setError('WhatsApp number is required');
      return false;
    }
    if (!affiliateData.cityLocation.trim()) {
      setError('City/Location is required');
      return false;
    }
    if (!affiliateData.experience) {
      setError('Experience level is required');
      return false;
    }
    return true;
  };

  const handleAffiliateSubmit = async () => {
    if (!validateAffiliateForm()) return;

    setLoading(true);
    setError('');
    try {
      const response = await fetch('http://127.0.0.1:8510/affiliates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: affiliateData.fullName,
          phone: affiliateData.whatsappNumber,
          location: affiliateData.cityLocation,
          experience_level: affiliateData.experience,
          referral_code: affiliateData.referralCode || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create affiliate account');
      }

      const result = await response.json();
      setSuccess(true);
      setStep('confirmation');
      
      // Auto-redirect after 3 seconds
      setTimeout(() => {
        navigate('/affiliate/dashboard');
      }, 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Customer form handlers
  const handleCustomerInputChange = (field: keyof CustomerData, value: string) => {
    setCustomerData(prev => ({ ...prev, [field]: value }));
  };

  const validateCustomerForm = () => {
    if (!customerData.fullName.trim()) {
      setError('Full name is required');
      return false;
    }
    if (!customerData.phoneNumber.trim()) {
      setError('Phone number is required');
      return false;
    }
    if (!customerData.email.trim()) {
      setError('Email is required');
      return false;
    }
    if (!customerData.email.includes('@')) {
      setError('Please enter a valid email');
      return false;
    }
    return true;
  };

  const handleCustomerSubmit = async () => {
    if (!validateCustomerForm()) return;

    setLoading(true);
    setError('');
    try {
      const response = await fetch('http://127.0.0.1:8500/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          identifier: customerData.email,
          password: '', // To be set separately
          role: 'customer',
          full_name: customerData.fullName,
          phone: customerData.phoneNumber,
          language: customerData.preferredLanguage,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create customer account');
      }

      const result = await response.json();
      setSuccess(true);
      setStep('confirmation');
      
      // Auto-redirect after 3 seconds
      setTimeout(() => {
        navigate('/');
      }, 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 flex items-center justify-center">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Welcome to NTheemba</h1>
          <p className="text-lg text-gray-600">Choose your role to get started</p>
        </div>

        {/* Role Selection Step */}
        {step === 'role-selection' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* MSME Card */}
            <Card 
              className="cursor-pointer hover:shadow-lg transition-all transform hover:scale-105"
              onClick={() => handleRoleSelect('msme')}
            >
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Building2 className="h-6 w-6 text-blue-600" />
                  </div>
                  <CardTitle>Business Owner</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base mb-4">
                  Run your store or shop on our platform
                </CardDescription>
                <ul className="text-sm space-y-2 text-gray-600 mb-4">
                  <li>✓ Manage products</li>
                  <li>✓ Track orders</li>
                  <li>✓ Process payments</li>
                  <li>✓ Connect with affiliates</li>
                </ul>
                <Button className="w-full" variant="outline">
                  Start as MSME <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </CardContent>
            </Card>

            {/* Affiliate Card */}
            <Card 
              className="cursor-pointer hover:shadow-lg transition-all transform hover:scale-105"
              onClick={() => handleRoleSelect('affiliate')}
            >
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <Share2 className="h-6 w-6 text-green-600" />
                  </div>
                  <CardTitle>Affiliate</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base mb-4">
                  Earn commissions promoting products
                </CardDescription>
                <ul className="text-sm space-y-2 text-gray-600 mb-4">
                  <li>✓ Generate links</li>
                  <li>✓ Track clicks</li>
                  <li>✓ Earn commissions</li>
                  <li>✓ Join campaigns</li>
                </ul>
                <Button className="w-full" variant="outline">
                  Start as Affiliate <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </CardContent>
            </Card>

            {/* Customer Card */}
            <Card 
              className="cursor-pointer hover:shadow-lg transition-all transform hover:scale-105"
              onClick={() => handleRoleSelect('customer')}
            >
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    <Users className="h-6 w-6 text-purple-600" />
                  </div>
                  <CardTitle>Customer</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base mb-4">
                  Shop and buy from local businesses
                </CardDescription>
                <ul className="text-sm space-y-2 text-gray-600 mb-4">
                  <li>✓ Browse products</li>
                  <li>✓ Make purchases</li>
                  <li>✓ Track orders</li>
                  <li>✓ Easy payments</li>
                </ul>
                <Button className="w-full" variant="outline">
                  Start Shopping <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Form Steps */}
        {step === 'form' && selectedRole === 'msme' && (
          <Card>
            <CardHeader>
              <CardTitle>Business Information</CardTitle>
              <CardDescription>Tell us about your business</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="businessName">Business Name *</Label>
                <Input
                  id="businessName"
                  placeholder="e.g., Rajesh's Electronics"
                  value={msmeData.businessName}
                  onChange={(e) => handleMsmeInputChange('businessName', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="ownerName">Owner Name *</Label>
                <Input
                  id="ownerName"
                  placeholder="e.g., Rajesh Kumar"
                  value={msmeData.ownerName}
                  onChange={(e) => handleMsmeInputChange('ownerName', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="businessPhone">Business Phone *</Label>
                <Input
                  id="businessPhone"
                  placeholder="e.g., 260973456789"
                  value={msmeData.businessPhone}
                  onChange={(e) => handleMsmeInputChange('businessPhone', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="businessType">Business Type *</Label>
                <select
                  id="businessType"
                  aria-label="Business Type"
                  className="w-full px-3 py-2 border rounded-md"
                  value={msmeData.businessType}
                  onChange={(e) => handleMsmeInputChange('businessType', e.target.value)}
                >
                  <option value="">Select a type</option>
                  <option value="retail">Retail Store</option>
                  <option value="electronics">Electronics</option>
                  <option value="grocery">Grocery</option>
                  <option value="fashion">Fashion</option>
                  <option value="food">Food & Beverages</option>
                  <option value="services">Services</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  placeholder="e.g., Lusaka, Zambia"
                  value={msmeData.location}
                  onChange={(e) => handleMsmeInputChange('location', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Business Description</Label>
                <textarea
                  id="description"
                  placeholder="Tell us about your business..."
                  className="w-full px-3 py-2 border rounded-md"
                  rows={4}
                  value={msmeData.description}
                  onChange={(e) => handleMsmeInputChange('description', e.target.value)}
                />
              </div>

              <div className="flex gap-2 pt-4">
                <Button variant="outline" onClick={handleBackToRoles} disabled={loading}>
                  Back
                </Button>
                <Button onClick={handleMsmeSubmit} disabled={loading} className="flex-1">
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    'Create Business Account'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 'form' && selectedRole === 'affiliate' && (
          <Card>
            <CardHeader>
              <CardTitle>Affiliate Registration</CardTitle>
              <CardDescription>Start earning commissions today</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="fullName">Full Name *</Label>
                <Input
                  id="fullName"
                  placeholder="e.g., John Doe"
                  value={affiliateData.fullName}
                  onChange={(e) => handleAffiliateInputChange('fullName', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="whatsappNumber">WhatsApp Number *</Label>
                <Input
                  id="whatsappNumber"
                  placeholder="e.g., 260973456789"
                  value={affiliateData.whatsappNumber}
                  onChange={(e) => handleAffiliateInputChange('whatsappNumber', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="cityLocation">City/Location *</Label>
                <Input
                  id="cityLocation"
                  placeholder="e.g., Lusaka"
                  value={affiliateData.cityLocation}
                  onChange={(e) => handleAffiliateInputChange('cityLocation', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="experience">Experience Level *</Label>
                <select
                  id="experience"
                  aria-label="Experience Level"
                  className="w-full px-3 py-2 border rounded-md"
                  value={affiliateData.experience}
                  onChange={(e) => handleAffiliateInputChange('experience', e.target.value)}
                >
                  <option value="">Select experience level</option>
                  <option value="beginner">Beginner (0-6 months)</option>
                  <option value="intermediate">Intermediate (6-12 months)</option>
                  <option value="advanced">Advanced (1+ years)</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="referralCode">Referral Code (Optional)</Label>
                <Input
                  id="referralCode"
                  placeholder="If you were referred by another affiliate"
                  value={affiliateData.referralCode}
                  onChange={(e) => handleAffiliateInputChange('referralCode', e.target.value)}
                />
              </div>

              <div className="flex gap-2 pt-4">
                <Button variant="outline" onClick={handleBackToRoles} disabled={loading}>
                  Back
                </Button>
                <Button onClick={handleAffiliateSubmit} disabled={loading} className="flex-1">
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    'Create Affiliate Account'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 'form' && selectedRole === 'customer' && (
          <Card>
            <CardHeader>
              <CardTitle>Customer Registration</CardTitle>
              <CardDescription>Create your customer account</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="customerName">Full Name *</Label>
                <Input
                  id="customerName"
                  placeholder="e.g., Jane Smith"
                  value={customerData.fullName}
                  onChange={(e) => handleCustomerInputChange('fullName', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="customerPhone">Phone Number *</Label>
                <Input
                  id="customerPhone"
                  placeholder="e.g., 260973456789"
                  value={customerData.phoneNumber}
                  onChange={(e) => handleCustomerInputChange('phoneNumber', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="customerEmail">Email Address *</Label>
                <Input
                  id="customerEmail"
                  type="email"
                  placeholder="e.g., jane@example.com"
                  value={customerData.email}
                  onChange={(e) => handleCustomerInputChange('email', e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="language">Preferred Language</Label>
                <select
                  id="language"
                  aria-label="Preferred Language"
                  className="w-full px-3 py-2 border rounded-md"
                  value={customerData.preferredLanguage}
                  onChange={(e) => handleCustomerInputChange('preferredLanguage', e.target.value)}
                >
                  <option value="en">English</option>
                  <option value="ny">Nyanja</option>
                  <option value="bemba">Bemba</option>
                </select>
              </div>

              <div className="bg-blue-50 p-4 rounded-md">
                <p className="text-sm text-gray-600">
                  By signing up, you agree to our Terms of Service and Privacy Policy.
                </p>
              </div>

              <div className="flex gap-2 pt-4">
                <Button variant="outline" onClick={handleBackToRoles} disabled={loading}>
                  Back
                </Button>
                <Button onClick={handleCustomerSubmit} disabled={loading} className="flex-1">
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    'Create Customer Account'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Confirmation Step */}
        {step === 'confirmation' && success && (
          <Card className="bg-green-50 border-green-200">
            <CardContent className="pt-8">
              <div className="text-center">
                <div className="flex justify-center mb-4">
                  <CheckCircle className="h-16 w-16 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold text-green-900 mb-2">Success!</h2>
                <p className="text-green-700 mb-4">
                  Your account has been created successfully.
                </p>
                <p className="text-sm text-green-600">
                  Redirecting to your dashboard in a few seconds...
                </p>
                <Badge className="mt-4">{selectedRole?.toUpperCase()} Account Created</Badge>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Onboarding;

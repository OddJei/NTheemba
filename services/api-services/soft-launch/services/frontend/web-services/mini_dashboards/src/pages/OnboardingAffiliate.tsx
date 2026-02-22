import { useState, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { affiliateOnboard } from '@/lib/clients';
import { ArrowLeft, ArrowRight, CheckCircle, User, Settings, Zap, Plus } from "lucide-react";

type Step = 'profile' | 'preferences' | 'complete';

interface ProfileData {
  fullName: string;
  email: string;
  phone: string;
  location: string;
  termsAccepted: boolean;
}

interface PreferencesData {
  categories: string[];
  commissionPreference: string;
  bio: string;
}

const OnboardingAffiliate = () => {
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

  const [preferences, setPreferences] = useState<PreferencesData>({
    categories: [],
    commissionPreference: 'high-volume',
    bio: ''
  });

  const categories = [
    { id: 'beauty', label: 'Beauty & Personal Care', icon: '💄' },
    { id: 'food', label: 'Food & Beverages', icon: '🍛' },
    { id: 'fashion', label: 'Fashion & Accessories', icon: '👔' },
    { id: 'furniture', label: 'Home & Furniture', icon: '🪑' },
    { id: 'tech', label: 'Tech & Electronics', icon: '📱' },
    { id: 'crafts', label: 'Crafts & Artisan', icon: '🎨' }
  ];

  const handleProfileChange = (field: keyof ProfileData, value: string | boolean) => {
    setProfile(prev => ({ ...prev, [field]: value }));
  };

  const handleCategoryToggle = (categoryId: string) => {
    setPreferences(prev => ({
      ...prev,
      categories: prev.categories.includes(categoryId)
        ? prev.categories.filter(c => c !== categoryId)
        : [...prev.categories, categoryId]
    }));
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
    setStep('preferences');
  };

  const handlePreferencesSubmit = async () => {
    if (preferences.categories.length === 0) {
      alert('Please select at least one product category');
      return;
    }

    setIsSubmitting(true);
    try {
      await affiliateOnboard({ profile, preferences });
      setStep('complete');
    } catch (error) {
      alert('Failed to complete onboarding. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCompleteOnboarding = () => {
    navigate('/affiliate');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#035688]/10 to-[#F38D1C]/5">
      {/* Header */}
      <header className="border-b bg-[#FEF6ED]">
        <div className="container mx-auto px-4 py-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')} className="text-[#035688]">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <h1 className="text-2xl font-bold mt-4 text-[#270A01]">Affiliate Program Onboarding</h1>
          <p className="text-sm text-[#C04208]">Join our network of successful affiliates</p>
        </div>
      </header>

      {/* Progress Indicator */}
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-center gap-8 mb-8">
          <div className={`flex flex-col items-center gap-2 ${step === 'profile' || step === 'preferences' || step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
              step === 'profile' || step === 'preferences' || step === 'complete' ? 'border-[#035688] bg-[#035688]/10' : 'border-muted'
            }`}>
              <User className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Profile</span>
          </div>

          <div className={`w-16 h-1 rounded-full ${step === 'preferences' || step === 'complete' ? 'bg-[#035688]' : 'bg-muted'}`} />

          <div className={`flex flex-col items-center gap-2 ${step === 'preferences' || step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
            <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 ${
              step === 'preferences' || step === 'complete' ? 'border-[#035688] bg-[#035688]/10' : 'border-muted'
            }`}>
              <Settings className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">Preferences</span>
          </div>

          <div className={`w-16 h-1 rounded-full ${step === 'complete' ? 'bg-[#035688]' : 'bg-muted'}`} />

          <div className={`flex flex-col items-center gap-2 ${step === 'complete' ? 'text-[#035688]' : 'text-muted-foreground'}`}>
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
              <CardTitle>Complete Your Profile</CardTitle>
              <CardDescription>Help us get to know you better</CardDescription>
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
                    placeholder="john@example.com"
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

        {step === 'preferences' && (
          <Card className="max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle>Set Your Preferences</CardTitle>
              <CardDescription>Choose categories you'd like to promote</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label className="text-base font-semibold mb-4 block">Product Categories *</Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => handleCategoryToggle(cat.id)}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${
                        preferences.categories.includes(cat.id)
                          ? 'border-[#035688] bg-[#035688]/10'
                          : 'border-muted hover:border-[#035688]/50'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-2xl">{cat.icon}</span>
                        <span className="font-medium">{cat.label}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <Label htmlFor="commission">Commission Preference</Label>
                <select
                  id="commission"
                  title="Commission Preference"
                  value={preferences.commissionPreference}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setPreferences(prev => ({ ...prev, commissionPreference: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="high-volume">High Volume (5-10% commission)</option>
                  <option value="balanced">Balanced (10-15% commission)</option>
                  <option value="high-value">High Value (15%+ commission)</option>
                </select>
              </div>

              <div>
                <Label htmlFor="bio">About You (Optional)</Label>
                <Textarea
                  id="bio"
                  placeholder="Tell us about your audience and why you're interested in affiliate marketing..."
                  value={preferences.bio}
                  onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setPreferences(prev => ({ ...prev, bio: e.target.value }))}
                  className="h-32"
                />
              </div>

              <div className="flex justify-between gap-4">
                <Button variant="outline" onClick={() => setStep('profile')}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
                <Button onClick={handlePreferencesSubmit} disabled={isSubmitting} className="bg-[#035688] hover:bg-[#0A3F5F] text-white">
                  {isSubmitting ? 'Completing...' : 'Complete Setup'}
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
                <h2 className="text-2xl font-bold mb-2 text-[#270A01]">Welcome to the Affiliate Program!</h2>
                <p className="text-muted-foreground">
                  Your profile is ready. Start promoting products and earn commissions today.
                </p>
              </div>

              <div className="bg-[#F38D1C]/10 border border-[#F38D1C]/20 rounded-lg p-4 text-left">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-[#F38D1C]" />
                  What's next?
                </h3>
                <ul className="text-sm space-y-1 text-muted-foreground">
                  <li>✓ Browse available products in your dashboard</li>
                  <li>✓ Generate unique affiliate links for products</li>
                  <li>✓ Share links with your audience</li>
                  <li>✓ Earn commissions when customers purchase</li>
                  <li>✓ Track your earnings in real-time</li>
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

export default OnboardingAffiliate;

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, ShoppingBag } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { customerOnboard, type CustomerOnboardRequest } from '@/lib/clients';

type Step = 'profile' | 'complete';

interface ProfileData {
  fullName: string;
  location: string;
  phone: string;
  termsAccepted: boolean;
}

export default function OnboardingCustomer() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('profile');
  const [profileData, setProfileData] = useState<ProfileData>({
    fullName: '',
    location: '',
    phone: '',
    termsAccepted: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stepConfig: Record<Step, { title: string; description: string; progress: number }> = {
    profile: {
      title: 'Welcome!',
      description: 'Tell us a bit about yourself',
      progress: 50,
    },
    complete: {
      title: 'All Set!',
      description: 'Your customer account is ready',
      progress: 100,
    },
  };

  const handleProfileChange = (field: keyof ProfileData, value: string | boolean) => {
    setProfileData((prev) => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleNext = async () => {
    if (step === 'profile') {
      // Validate profile fields
      if (!profileData.fullName.trim()) {
        setError('Please enter your full name');
        return;
      }
      if (!profileData.location.trim()) {
        setError('Please enter your location');
        return;
      }
      if (!profileData.phone.trim()) {
        setError('Please enter your phone number');
        return;
      }
      if (!profileData.termsAccepted) {
        setError('Please accept the terms and conditions');
        return;
      }

      // Submit onboarding
      try {
        setIsLoading(true);
        setError(null);

        const payload: CustomerOnboardRequest = {
          profile: {
            fullName: profileData.fullName,
            location: profileData.location,
            phone: profileData.phone,
          },
          termsAccepted: profileData.termsAccepted,
        };

        await customerOnboard(payload);
        setStep('complete');
      } catch (err: any) {
        setError(err.message || 'Onboarding failed. Please try again.');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleFinish = () => {
    // Navigate to customer dashboard (or wherever appropriate)
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 mobile:p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6 mobile:mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 mobile:w-16 mobile:h-16 bg-blue-600 text-white rounded-full mb-4">
            <ShoppingBag className="w-6 h-6 mobile:w-8 mobile:h-8" />
          </div>
          <h1 className="text-2xl mobile:text-3xl font-bold text-gray-900 mb-2">
            Customer Onboarding
          </h1>
          <p className="text-sm mobile:text-base text-gray-600">
            {stepConfig[step].description}
          </p>
        </div>

        {/* Progress */}
        <div className="mb-6 mobile:mb-8">
          <Progress value={stepConfig[step].progress} className="h-2" />
          <p className="text-xs mobile:text-sm text-gray-500 text-center mt-2">
            Step {step === 'profile' ? '1' : '2'} of 2
          </p>
        </div>

        {/* Content */}
        {step === 'profile' && (
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Your Profile</CardTitle>
              <CardDescription>Basic information to get started</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 mobile:space-y-5">
              <div className="space-y-2">
                <Label htmlFor="fullName">Full Name *</Label>
                <Input
                  id="fullName"
                  type="text"
                  placeholder="Enter your full name"
                  value={profileData.fullName}
                  onChange={(e) => handleProfileChange('fullName', e.target.value)}
                  className="touch-target"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="location">Location *</Label>
                <Input
                  id="location"
                  type="text"
                  placeholder="City, Country"
                  value={profileData.location}
                  onChange={(e) => handleProfileChange('location', e.target.value)}
                  className="touch-target"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone">Phone Number *</Label>
                <Input
                  id="phone"
                  type="tel"
                  placeholder="+1234567890"
                  value={profileData.phone}
                  onChange={(e) => handleProfileChange('phone', e.target.value)}
                  className="touch-target"
                />
              </div>

              <div className="flex items-start space-x-3 pt-4 border-t">
                <Checkbox
                  id="terms"
                  checked={profileData.termsAccepted}
                  onChange={(e) => handleProfileChange('termsAccepted', e.target.checked)}
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

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
                  {error}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {step === 'complete' && (
          <Card className="shadow-lg">
            <CardContent className="pt-6 pb-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 mobile:w-20 mobile:h-20 bg-green-100 text-green-600 rounded-full mb-4 mobile:mb-6">
                <Check className="w-8 h-8 mobile:w-10 mobile:h-10" />
              </div>
              <h2 className="text-xl mobile:text-2xl font-bold text-gray-900 mb-2">
                Welcome, {profileData.fullName}!
              </h2>
              <p className="text-sm mobile:text-base text-gray-600 mb-6 mobile:mb-8">
                Your customer account has been created successfully. You can now start shopping and exploring our products.
              </p>
              <Button
                onClick={handleFinish}
                className="touch-target-large w-full mobile:w-auto mobile:min-w-[200px]"
              >
                Start Shopping
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Navigation */}
        {step === 'profile' && (
          <div className="mt-6 flex justify-between items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => navigate(-1)}
              className="touch-target"
              disabled={isLoading}
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>

            <Button
              onClick={handleNext}
              className="touch-target"
              disabled={isLoading}
            >
              {isLoading ? 'Submitting...' : 'Complete'}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Progress } from '../../components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avater';
import { Camera, HelpCircle, CheckCircle, Clock, XCircle } from 'lucide-react';

// Dummy KYC status for demonstration
const KYC_STATUS = {
  pending: 'Pending',
  verified: 'Verified',
  failed: 'Failed',
};

const initialProfile = {
  name: '',
  msisdn: '',
  payoutChannel: '',
  payoutHandle: '',
  consent: false,
  kycStatus: 'pending',
  avatar: null,
  lastLogin: '2025-08-30T10:30:00Z',
  joinDate: '2025-08-15T14:20:00Z',
};


export default function AffiliateProfile() {
  const [profile, setProfile] = useState(initialProfile);
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState("");
  const [avatarPreview, setAvatarPreview] = useState(null);

  const getKycProgress = () => {
    const steps = [
      { label: 'Basic Info', completed: !!profile.name && !!profile.msisdn },
      { label: 'Payout Details', completed: !!profile.payoutChannel && !!profile.payoutHandle },
      { label: 'Consent', completed: profile.consent },
      { label: 'Document Upload', completed: profile.kycStatus === 'verified' },
    ];
    const completed = steps.filter(step => step.completed).length;
    return { completed, total: steps.length, percentage: (completed / steps.length) * 100, steps };
  };

  const formatLastSeen = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = Math.floor((now - date) / (1000 * 60 * 60));
    
    if (diffInHours < 1) return 'Active now';
    if (diffInHours < 24) return `${diffInHours} hours ago`;
    if (diffInHours < 48) return 'Yesterday';
    return date.toLocaleDateString();
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        setAvatarPreview(reader.result);
        setProfile(prev => ({ ...prev, avatar: file }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setProfile((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleEdit = () => setEditing(true);
  const handleCancel = () => {
    setEditing(false);
    setMessage("");
    setAvatarPreview(null);
  };
  const handleSave = (e) => {
    e.preventDefault();
    // TODO: Add API call here
    setEditing(false);
    setMessage("Profile updated successfully!");
  };

  const kycProgress = getKycProgress();

  return (
    <TooltipProvider>
      <div className="w-full px-2 sm:px-4 max-w-2xl mx-auto mt-4 sm:mt-8 space-y-4">
        {/* Profile Header with Avatar */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Affiliate Profile</span>
              <div className="text-sm text-muted-foreground">
                Last seen: {formatLastSeen(profile.lastLogin)}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row items-center gap-4 mb-6">
              <div className="relative">
                <Avatar className="w-20 h-20 sm:w-24 sm:h-24">
                  <AvatarImage src={avatarPreview || profile.avatar} />
                  <AvatarFallback className="text-lg">{profile.name ? profile.name.charAt(0).toUpperCase() : 'A'}</AvatarFallback>
                </Avatar>
                {editing && (
                  <>
                    <input
                      type="file"
                      id="avatar-upload"
                      accept="image/*"
                      onChange={handleAvatarChange}
                      className="hidden"
                    />
                    <label
                      htmlFor="avatar-upload"
                      className="absolute bottom-0 right-0 bg-primary text-primary-foreground p-2 rounded-full cursor-pointer hover:bg-primary/90"
                    >
                      <Camera className="w-4 h-4" />
                    </label>
                  </>
                )}
              </div>
              <div className="text-center sm:text-left">
                <h3 className="text-xl font-semibold">{profile.name || 'Affiliate User'}</h3>
                <p className="text-muted-foreground">Member since {new Date(profile.joinDate).toLocaleDateString()}</p>
              </div>
            </div>
            
            {/* KYC Progress */}
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-2">
                <Label className="font-medium">KYC Progress:</Label>
                <span className={`text-sm font-semibold flex items-center gap-1 ${
                  profile.kycStatus === "verified" ? "text-green-600" :
                  profile.kycStatus === "failed" ? "text-red-600" : "text-yellow-600"
                }`}>
                  {profile.kycStatus === "verified" && <CheckCircle className="w-4 h-4" />}
                  {profile.kycStatus === "failed" && <XCircle className="w-4 h-4" />}
                  {profile.kycStatus === "pending" && <Clock className="w-4 h-4" />}
                  {KYC_STATUS[profile.kycStatus]}
                </span>
              </div>
              <div className="space-y-2">
                <Progress value={kycProgress.percentage} className="h-2" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{kycProgress.completed}/{kycProgress.total} steps completed</span>
                  <span>{Math.round(kycProgress.percentage)}%</span>
                </div>
              </div>
            </div>
            
            {editing ? (
              <form onSubmit={handleSave} className="space-y-4">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="name">Name</Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="w-4 h-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Enter your full legal name as it appears on your ID</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id="name"
                    name="name"
                    value={profile.name}
                    onChange={handleChange}
                    required
                    className="w-full"
                    placeholder="Enter your full name"
                  />
                </div>
                
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="msisdn">Mobile Number (MSISDN)</Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="w-4 h-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Your phone number for account verification and payouts</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id="msisdn"
                    name="msisdn"
                    value={profile.msisdn}
                    onChange={handleChange}
                    required
                    className="w-full"
                    inputMode="tel"
                    placeholder="+260 XXX XXX XXX"
                  />
                </div>
                
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="payoutChannel">Payout Channel</Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="w-4 h-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Choose your preferred payment method (Mobile Money, Bank, etc.)</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id="payoutChannel"
                    name="payoutChannel"
                    value={profile.payoutChannel}
                    onChange={handleChange}
                    required
                    className="w-full"
                    placeholder="e.g., MTN Mobile Money"
                  />
                </div>
                
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="payoutHandle">Payout Handle</Label>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="w-4 h-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Account number or phone number for receiving payments</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    id="payoutHandle"
                    name="payoutHandle"
                    value={profile.payoutHandle}
                    onChange={handleChange}
                    required
                    className="w-full"
                    placeholder="Account number or phone number"
                  />
                </div>
                
                <div className="flex items-center flex-wrap gap-2">
                  <input
                    type="checkbox"
                    id="consent"
                    name="consent"
                    checked={profile.consent}
                    onChange={handleChange}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="consent" className="ml-2 flex items-center gap-2">
                    I consent to data processing
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="w-4 h-4 text-muted-foreground" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Required for account verification and payment processing</p>
                      </TooltipContent>
                    </Tooltip>
                  </Label>
                </div>
                
                <div className="flex flex-col sm:flex-row gap-2">
                  <Button type="submit" className="w-full sm:w-auto">Save Profile</Button>
                  <Button type="button" variant="secondary" onClick={handleCancel} className="w-full sm:w-auto">Cancel</Button>
                </div>
              </form>
            ) : (
              <div className="space-y-3">
                <div>
                  <span className="font-medium">Name:</span>{" "}
                  {profile.name || <span className="text-muted-foreground">Not set</span>}
                </div>
                <div>
                  <span className="font-medium">Mobile Number:</span>{" "}
                  {profile.msisdn || <span className="text-muted-foreground">Not set</span>}
                </div>
                <div>
                  <span className="font-medium">Payout Channel:</span>{" "}
                  {profile.payoutChannel || <span className="text-muted-foreground">Not set</span>}
                </div>
                <div>
                  <span className="font-medium">Payout Handle:</span>{" "}
                  {profile.payoutHandle || <span className="text-muted-foreground">Not set</span>}
                </div>
                <div>
                  <span className="font-medium">Consent:</span>{" "}
                  {profile.consent ? "Yes" : "No"}
                </div>
                <Button className="mt-4 w-full sm:w-auto" onClick={handleEdit}>
                  Edit Profile
                </Button>
              </div>
            )}
            {message && <div className="mt-4 text-green-600 font-medium">{message}</div>}
          </CardContent>
        </Card>
        
        {/* KYC Steps Details */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Verification Steps</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {kycProgress.steps.map((step, index) => (
                <div key={step.label} className="flex items-center justify-between p-3 rounded-lg border">
                  <div className="flex items-center gap-3">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-sm ${
                      step.completed ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {step.completed ? <CheckCircle className="w-4 h-4" /> : index + 1}
                    </div>
                    <span className="font-medium">{step.label}</span>
                  </div>
                  <span className={`text-sm ${step.completed ? 'text-green-600' : 'text-muted-foreground'}`}>
                    {step.completed ? 'Complete' : 'Pending'}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}

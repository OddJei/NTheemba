import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Lock, 
  Star, 
  Crown, 
  ArrowRight, 
  Gift,
  Zap,
  TrendingUp
} from 'lucide-react';
import { UserRole, UserTier } from '@/lib/feature-gates';

interface UpgradePromptProps {
  featureName: string;
  description: string;
  requiredTier: UserTier;
  userRole: UserRole;
  variant?: 'card' | 'inline' | 'modal';
  showFeaturePreview?: boolean;
  onUpgrade?: () => void;
  className?: string;
}

const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  featureName,
  description,
  requiredTier,
  userRole,
  variant = 'card',
  showFeaturePreview = true,
  onUpgrade,
  className = ''
}) => {
  const getTierInfo = (tier: UserTier) => {
    const info = {
      pro: {
        name: 'Pro',
        icon: Star,
        color: 'text-green-600',
        bgColor: 'bg-green-50',
        borderColor: 'border-green-200',
        price: userRole === 'msme' ? 'ZMW 199/month' : 'ZMW 99/month'
      },
      'pro-plus': {
        name: 'Pro+',
        icon: Crown,
        color: 'text-purple-600',
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-200',
        price: userRole === 'msme' ? 'ZMW 399/month' : 'N/A'
      },
      basic: {
        name: 'Basic',
        icon: Gift,
        color: 'text-gray-600',
        bgColor: 'bg-gray-50',
        borderColor: 'border-gray-200',
        price: 'Free'
      }
    };
    return info[tier];
  };

  const tierInfo = getTierInfo(requiredTier);
  const TierIcon = tierInfo.icon;

  const getBenefits = () => {
    if (userRole === 'msme') {
      return requiredTier === 'pro' 
        ? ['Advanced bot analytics', 'Custom bot personality', 'Priority support', 'Custom reports']
        : ['White-label branding', 'Multi-language support', 'Advanced integrations', 'Dedicated manager'];
    } else {
      return requiredTier === 'pro'
        ? ['Pro-only campaigns', 'Branded links', 'Weekly payouts', 'Advanced analytics']
        : [];
    }
  };

  const benefits = getBenefits();

  if (variant === 'inline') {
    return (
      <Alert className={`${tierInfo.borderColor} ${tierInfo.bgColor} ${className}`}>
        <Lock className="h-4 w-4" />
        <AlertDescription className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <TierIcon className={`w-4 h-4 ${tierInfo.color}`} />
            <span className="font-medium">
              {featureName} requires {tierInfo.name}
            </span>
          </div>
          <Button 
            size="sm" 
            className={`${tierInfo.color} hover:${tierInfo.color}/80`}
            variant="ghost"
            onClick={onUpgrade}
          >
            Upgrade
            <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (variant === 'modal') {
    return (
      <div className={`text-center p-6 ${className}`}>
        <div className={`mx-auto w-16 h-16 ${tierInfo.bgColor} rounded-full flex items-center justify-center mb-4`}>
          <Lock className="w-8 h-8 text-gray-400" />
        </div>
        <h3 className="text-xl font-bold mb-2">Unlock {featureName}</h3>
        <p className="text-gray-600 mb-6">{description}</p>
        
        <div className={`p-4 ${tierInfo.bgColor} rounded-lg mb-6`}>
          <div className="flex items-center justify-center space-x-2 mb-2">
            <TierIcon className={`w-5 h-5 ${tierInfo.color}`} />
            <span className="font-semibold">{tierInfo.name} Plan</span>
          </div>
          <div className="text-2xl font-bold mb-2">{tierInfo.price}</div>
          <div className="text-sm text-gray-600">Unlock this feature and more</div>
        </div>

        <Button 
          className="w-full mb-4"
          onClick={onUpgrade}
        >
          Upgrade to {tierInfo.name}
          <TierIcon className="w-4 h-4 ml-2" />
        </Button>
        
        <div className="text-xs text-gray-500">
          Cancel anytime • 30-day money-back guarantee
        </div>
      </div>
    );
  }

  // Default: card variant
  return (
    <Card className={`${tierInfo.borderColor} ${className}`}>
      <CardHeader className="text-center">
        <div className={`mx-auto w-12 h-12 ${tierInfo.bgColor} rounded-full flex items-center justify-center mb-2`}>
          <Lock className="w-6 h-6 text-gray-400" />
        </div>
        <CardTitle className="text-lg">
          {featureName} 
          <Badge variant="outline" className={`ml-2 ${tierInfo.color} border-current`}>
            <TierIcon className="w-3 h-3 mr-1" />
            {tierInfo.name}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-gray-600 text-center mb-4">{description}</p>
        
        {showFeaturePreview && benefits.length > 0 && (
          <div className="mb-6">
            <h4 className="font-semibold mb-3 flex items-center">
              <Zap className={`w-4 h-4 mr-2 ${tierInfo.color}`} />
              What you'll get with {tierInfo.name}:
            </h4>
            <ul className="space-y-2 text-sm">
              {benefits.map((benefit, index) => (
                <li key={index} className="flex items-center space-x-2">
                  <TrendingUp className={`w-3 h-3 ${tierInfo.color}`} />
                  <span>{benefit}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className={`p-3 ${tierInfo.bgColor} rounded-lg mb-4 text-center`}>
          <div className="font-semibold mb-1">Starting at {tierInfo.price}</div>
          <div className="text-sm text-gray-600">Billed monthly • Cancel anytime</div>
        </div>

        <Button 
          className="w-full"
          onClick={onUpgrade}
        >
          Upgrade Now
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
        
        <div className="text-center mt-3">
          <button 
            className="text-xs text-gray-500 hover:text-gray-700 underline"
            onClick={() => console.log('Show feature demo')}
          >
            See how this works
          </button>
        </div>
      </CardContent>
    </Card>
  );
};

export default UpgradePrompt;

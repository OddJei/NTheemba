import React from 'react';
import { useFeatureGate, UserTier, UserRole } from '@/lib/feature-gates';
import UpgradePrompt from '@/components/ui/upgrade-prompt';

interface FeatureGateProps {
  featureId: string;
  user: {
    id: string;
    tier: UserTier;
    role: UserRole;
    subscriptionActive: boolean;
    trialEndsAt?: Date;
  };
  fallback?: React.ReactNode;
  upgradePromptVariant?: 'card' | 'inline' | 'modal';
  showUpgradePrompt?: boolean;
  children: React.ReactNode;
  onUpgrade?: () => void;
}

const FeatureGate: React.FC<FeatureGateProps> = ({
  featureId,
  user,
  fallback,
  upgradePromptVariant = 'card',
  showUpgradePrompt = true,
  children,
  onUpgrade
}) => {
  const featureGate = useFeatureGate(user);

  // If user has access, render the children
  if (featureGate.hasAccess(featureId)) {
    return <>{children}</>;
  }

  // If a custom fallback is provided, use it
  if (fallback) {
    return <>{fallback}</>;
  }

  // If upgrade prompt is disabled, don't render anything
  if (!showUpgradePrompt) {
    return null;
  }

  // Get feature details for the upgrade prompt
  const unavailableFeatures = featureGate.getUnavailableFeatures();
  const targetFeature = unavailableFeatures.find(f => f.id === featureId);

  if (!targetFeature) {
    // Feature not found or not applicable to this user role
    return null;
  }

  return (
    <UpgradePrompt
      featureName={targetFeature.name}
      description={targetFeature.description}
      requiredTier={targetFeature.requiredTier}
      userRole={user.role}
      variant={upgradePromptVariant}
      onUpgrade={onUpgrade}
    />
  );
};

export default FeatureGate;

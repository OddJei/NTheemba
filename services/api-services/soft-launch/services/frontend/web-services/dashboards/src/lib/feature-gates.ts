// Feature gating system for subscription-based access control

export type UserTier = 'basic' | 'pro' | 'pro-plus';
export type UserRole = 'msme' | 'affiliate';

interface FeatureGate {
  id: string;
  name: string;
  description: string;
  requiredTier: UserTier;
  roles: UserRole[];
  isActive: boolean;
}

// Feature definitions
export const FEATURES: Record<string, FeatureGate> = {
  // MSME Features
  ADVANCED_BOT_ANALYTICS: {
    id: 'advanced_bot_analytics',
    name: 'Advanced Bot Analytics',
    description: 'Detailed conversation insights and performance metrics',
    requiredTier: 'pro',
    roles: ['msme'],
    isActive: true
  },
  BOT_PERSONALITY_CUSTOMIZATION: {
    id: 'bot_personality_customization',
    name: 'Bot Personality Customization',
    description: 'Customize bot tone, responses, and personality traits',
    requiredTier: 'pro',
    roles: ['msme'],
    isActive: true
  },
  WHITE_LABEL_BRANDING: {
    id: 'white_label_branding',
    name: 'White Label Branding',
    description: 'Complete bot branding with custom logos and colors',
    requiredTier: 'pro-plus',
    roles: ['msme'],
    isActive: true
  },
  MULTI_LANGUAGE_SUPPORT: {
    id: 'multi_language_support',
    name: 'Multi-Language Support',
    description: 'Bot responses in multiple local languages',
    requiredTier: 'pro-plus',
    roles: ['msme'],
    isActive: true
  },
  ADVANCED_INTEGRATIONS: {
    id: 'advanced_integrations',
    name: 'Advanced Integrations',
    description: 'CRM, payment gateway, and third-party API integrations',
    requiredTier: 'pro-plus',
    roles: ['msme'],
    isActive: true
  },
  PRIORITY_SUPPORT: {
    id: 'priority_support',
    name: 'Priority Support',
    description: 'Dedicated support manager and priority ticket handling',
    requiredTier: 'pro',
    roles: ['msme'],
    isActive: true
  },
  CUSTOM_REPORTS: {
    id: 'custom_reports',
    name: 'Custom Reports',
    description: 'Build custom analytics reports and dashboards',
    requiredTier: 'pro',
    roles: ['msme'],
    isActive: true
  },

  // Affiliate Features
  PRO_CAMPAIGNS: {
    id: 'pro_campaigns',
    name: 'Pro-Only Campaigns',
    description: 'Access to exclusive high-commission campaigns',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  BRANDED_LINKS: {
    id: 'branded_links',
    name: 'Branded Short Links',
    description: 'Custom branded short links and bulk generation',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  CAMPAIGN_PRESETS: {
    id: 'campaign_presets',
    name: 'Campaign Presets',
    description: 'Save and reuse campaign configurations',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  TIER_INCENTIVES: {
    id: 'tier_incentives',
    name: 'Tier-based Incentives',
    description: 'Performance bonuses and tier advancement rewards',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  WEEKLY_PAYOUTS: {
    id: 'weekly_payouts',
    name: 'Weekly Payouts',
    description: 'Weekly payment processing instead of monthly',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  ADVANCED_ANALYTICS: {
    id: 'advanced_analytics',
    name: 'Advanced Analytics',
    description: 'Conversion funnels, audience insights, and optimization tips',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  CUSTOM_REPORT_BUILDER: {
    id: 'custom_report_builder',
    name: 'Custom Report Builder',
    description: 'Create custom performance and earnings reports',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  REFERRAL_BONUSES: {
    id: 'referral_bonuses',
    name: 'Referral Bonuses',
    description: 'Earn bonuses for referring new affiliates to the platform',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  API_ACCESS: {
    id: 'api_access',
    name: 'API Access',
    description: 'Full API access for integrations and automation',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  },
  DEDICATED_MANAGER: {
    id: 'dedicated_manager',
    name: 'Dedicated Success Manager',
    description: 'Personal affiliate success manager and priority support',
    requiredTier: 'pro',
    roles: ['affiliate'],
    isActive: true
  }
};

// User context (would typically come from auth/user state)
interface User {
  id: string;
  tier: UserTier;
  role: UserRole;
  subscriptionActive: boolean;
  trialEndsAt?: Date;
}

// Feature gate checker
export class FeatureGateService {
  private user: User;

  constructor(user: User) {
    this.user = user;
  }

  // Check if user has access to a specific feature
  hasAccess(featureId: string): boolean {
    const feature = FEATURES[featureId];
    if (!feature || !feature.isActive) return false;

    // Check role compatibility
    if (!feature.roles.includes(this.user.role)) return false;

    // Check subscription status
    if (!this.user.subscriptionActive && feature.requiredTier !== 'basic') {
      // Allow access during trial period
      if (this.user.trialEndsAt && new Date() < this.user.trialEndsAt) {
        return true;
      }
      return false;
    }

    // Check tier requirement
    return this.meetsTierRequirement(feature.requiredTier);
  }

  // Check if user's tier meets the requirement
  private meetsTierRequirement(requiredTier: UserTier): boolean {
    const tierHierarchy: Record<UserTier, number> = {
      'basic': 0,
      'pro': 1,
      'pro-plus': 2
    };

    return tierHierarchy[this.user.tier] >= tierHierarchy[requiredTier];
  }

  // Get features available to the user
  getAvailableFeatures(): FeatureGate[] {
    return Object.values(FEATURES).filter(feature => this.hasAccess(feature.id));
  }

  // Get features user doesn't have access to (for upselling)
  getUnavailableFeatures(): FeatureGate[] {
    return Object.values(FEATURES)
      .filter(feature => 
        feature.roles.includes(this.user.role) && 
        !this.hasAccess(feature.id)
      );
  }

  // Get upgrade suggestions based on user's role
  getUpgradeSuggestions(): { tier: UserTier; features: FeatureGate[] } | null {
    const unavailable = this.getUnavailableFeatures();
    
    if (unavailable.length === 0) return null;

    // Suggest the lowest tier that unlocks the most features
    const tierFeatureCount: Record<UserTier, number> = {
      'basic': 0,
      'pro': 0,
      'pro-plus': 0
    };

    unavailable.forEach(feature => {
      tierFeatureCount[feature.requiredTier]++;
    });

    // Find the tier with the most unlockable features
    const suggestedTier = Object.entries(tierFeatureCount)
      .sort(([,a], [,b]) => b - a)
      .find(([tier, count]) => count > 0)?.[0] as UserTier;

    if (!suggestedTier) return null;

    const suggestedFeatures = unavailable.filter(
      feature => feature.requiredTier === suggestedTier
    );

    return {
      tier: suggestedTier,
      features: suggestedFeatures
    };
  }
}

// React hook for feature gating
export const useFeatureGate = (user: User) => {
  const service = new FeatureGateService(user);
  
  return {
    hasAccess: (featureId: string) => service.hasAccess(featureId),
    getAvailableFeatures: () => service.getAvailableFeatures(),
    getUnavailableFeatures: () => service.getUnavailableFeatures(),
    getUpgradeSuggestions: () => service.getUpgradeSuggestions(),
    canAccessProCampaigns: () => service.hasAccess('PRO_CAMPAIGNS'),
    canUseBrandedLinks: () => service.hasAccess('BRANDED_LINKS'),
    canAccessAdvancedAnalytics: () => service.hasAccess('ADVANCED_ANALYTICS'),
    canCustomizeBotPersonality: () => service.hasAccess('BOT_PERSONALITY_CUSTOMIZATION'),
    canAccessWhiteLabeling: () => service.hasAccess('WHITE_LABEL_BRANDING'),
    canAccessPrioritySupport: () => service.hasAccess('PRIORITY_SUPPORT')
  };
};

// Commission rate calculator based on tier
export const getCommissionRate = (baseTier: UserTier, campaignType: 'standard' | 'pro'): number => {
  const baseRates = {
    standard: {
      basic: 0.05, // 5%
      pro: 0.05,   // 5%
      'pro-plus': 0.05
    },
    pro: {
      basic: 0, // No access to pro campaigns
      pro: 0.10, // 10%
      'pro-plus': 0.12 // 12%
    }
  };

  // Tier bonuses
  const tierBonus = baseTier === 'pro' || baseTier === 'pro-plus' ? 0.02 : 0; // +2%

  return baseRates[campaignType][baseTier] + tierBonus;
};

// Payout thresholds based on tier
export const getPayoutThreshold = (tier: UserTier): number => {
  const thresholds = {
    basic: 100, // ZMW 100
    pro: 50,    // ZMW 50
    'pro-plus': 50 // ZMW 50
  };
  
  return thresholds[tier];
};

// Payout frequency based on tier
export const getPayoutFrequency = (tier: UserTier): 'monthly' | 'weekly' => {
  return tier === 'basic' ? 'monthly' : 'weekly';
};

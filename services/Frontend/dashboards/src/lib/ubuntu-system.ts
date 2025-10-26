// Ubuntu Community is FREE - Business tools are subscription-based
// Ubuntu: "I am because we are" - Community access for all, premium tools for growth

export type UbuntuRole = 'msme' | 'affiliate' | 'msme-affiliate' | 'community-champion';
export type BusinessTier = 'basic' | 'pro' | 'pro-plus'; // For MSME and Affiliate tools
export type UbuntuTier = 'community-member' | 'ubuntu-champion'; // Ubuntu community tiers (free)

export interface UbuntuUser {
  id: string;
  name: string;
  roles: UbuntuRole[];
  businessTier: BusinessTier; // Paid subscription for business tools
  ubuntuTier: UbuntuTier; // Free Ubuntu community status
  location: {
    country: string;
    region: string;
    city: string;
  };
  joinedAt: Date;
  ubuntuScore: number; // Community contribution score
  africanValues: {
    community: number;    // How much they help others
    sharing: number;      // How often they share opportunities
    support: number;      // Support given to fellow African businesses
    growth: number;       // Personal and community growth contribution
  };
  businessSubscriptionActive: boolean; // For paid tools
  trialEndsAt?: Date;
}

// Ubuntu Community Actions (FREE for all)
export interface CommunityAction {
  id: string;
  type: 'share_opportunity' | 'mentor_business' | 'refer_customer' | 'collaborate' | 'celebrate_win' | 'provide_support';
  description: string;
  ubuntuPoints: number; // Points earned for community contribution
  requirements: {
    minUbuntuScore?: number;
    requiredRoles?: UbuntuRole[];
    tier?: UbuntuTier; // Free community tiers only
  };
  impact: {
    community: number;
    sharing: number;
    support: number;
    growth: number;
  };
}

// Business Tools (PAID - requires business subscription)
export interface BusinessTool {
  id: string;
  name: string;
  type: 'analytics' | 'marketing' | 'crm' | 'automation' | 'integration' | 'advanced-affiliate';
  description: string;
  tier: BusinessTier; // Requires paid subscription
  available: boolean;
  paywall: boolean;
}

// FREE Ubuntu Community Features
export const FREE_UBUNTU_FEATURES: Record<string, CommunityAction> = {
  COMMUNITY_CONNECT: {
    id: 'community_connect',
    type: 'collaborate',
    description: 'Connect with fellow African entrepreneurs',
    ubuntuPoints: 10,
    requirements: { tier: 'community-member' },
    impact: { community: 5, sharing: 0, support: 3, growth: 2 }
  },
  SHARE_OPPORTUNITY: {
    id: 'share_opportunity',
    type: 'share_opportunity',
    description: 'Share business opportunities with the community',
    ubuntuPoints: 15,
    requirements: { tier: 'community-member' },
    impact: { community: 3, sharing: 8, support: 2, growth: 2 }
  },
  MENTOR_SUPPORT: {
    id: 'mentor_support',
    type: 'mentor_business',
    description: 'Provide mentorship to new entrepreneurs',
    ubuntuPoints: 25,
    requirements: { tier: 'ubuntu-champion', minUbuntuScore: 100 },
    impact: { community: 4, sharing: 2, support: 6, growth: 8 }
  },
  CELEBRATE_WINS: {
    id: 'celebrate_wins',
    type: 'celebrate_win',
    description: 'Celebrate community successes and milestones',
    ubuntuPoints: 5,
    requirements: { tier: 'community-member' },
    impact: { community: 6, sharing: 3, support: 8, growth: 1 }
  },
  REFER_CUSTOMER: {
    id: 'refer_customer',
    type: 'refer_customer',
    description: 'Refer customers to fellow businesses',
    ubuntuPoints: 20,
    requirements: { tier: 'community-member' },
    impact: { community: 4, sharing: 6, support: 7, growth: 3 }
  },
  PROVIDE_SUPPORT: {
    id: 'provide_support',
    type: 'provide_support',
    description: 'Offer support during challenging times',
    ubuntuPoints: 30,
    requirements: { tier: 'community-member', minUbuntuScore: 50 },
    impact: { community: 8, sharing: 2, support: 9, growth: 4 }
  }
};

// PAID Business Tools (MSME and Affiliate subscriptions)
export const BUSINESS_TOOLS: Record<string, BusinessTool> = {
  ADVANCED_ANALYTICS: {
    id: 'advanced_analytics',
    name: 'Advanced Business Analytics',
    type: 'analytics',
    description: 'Detailed performance metrics and insights',
    tier: 'basic',
    available: false,
    paywall: true
  },
  MARKETING_AUTOMATION: {
    id: 'marketing_automation',
    name: 'Marketing Automation Suite',
    type: 'marketing',
    description: 'Automated marketing campaigns and funnels',
    tier: 'pro',
    available: false,
    paywall: true
  },
  CRM_INTEGRATION: {
    id: 'crm_integration',
    name: 'Customer Relationship Management',
    type: 'crm',
    description: 'Full CRM with customer tracking and management',
    tier: 'basic',
    available: false,
    paywall: true
  },
  WORKFLOW_AUTOMATION: {
    id: 'workflow_automation',
    name: 'Business Workflow Automation',
    type: 'automation',
    description: 'Automate repetitive business processes',
    tier: 'pro',
    available: false,
    paywall: true
  },
  THIRD_PARTY_INTEGRATIONS: {
    id: 'third_party_integrations',
    name: 'Third-Party Integrations',
    type: 'integration',
    description: 'Connect with external business tools and platforms',
    tier: 'pro-plus',
    available: false,
    paywall: true
  },
  ADVANCED_AFFILIATE_TOOLS: {
    id: 'advanced_affiliate_tools',
    name: 'Advanced Affiliate Management',
    type: 'advanced-affiliate',
    description: 'Multi-tier affiliate tracking and commission management',
    tier: 'pro',
    available: false,
    paywall: true
  }
};

// Ubuntu Score Calculation - Measuring Community Contribution (FREE)
export const calculateUbuntuScore = (user: UbuntuUser): number => {
  const { africanValues } = user;
  
  // Ubuntu score is weighted average of African values
  const weights = {
    community: 0.3,   // 30% - helping others
    sharing: 0.25,    // 25% - sharing opportunities
    support: 0.25,    // 25% - supporting fellow businesses
    growth: 0.2       // 20% - contributing to growth
  };

  return Math.round(
    (africanValues.community * weights.community) +
    (africanValues.sharing * weights.sharing) +
    (africanValues.support * weights.support) +
    (africanValues.growth * weights.growth)
  );
};

// Ubuntu Tier Advancement - Based on Community Contribution (FREE)
export const getNextUbuntuTier = (currentTier: UbuntuTier, ubuntuScore: number): UbuntuTier | null => {
  if (currentTier === 'community-member' && ubuntuScore >= 500) {
    return 'ubuntu-champion';
  }
  return null;
};

// Business Tool Access Check (PAID)
export const hasBusinessToolAccess = (
  user: UbuntuUser,
  toolId: keyof typeof BUSINESS_TOOLS
): boolean => {
  if (!user.businessSubscriptionActive) {
    return false;
  }
  
  const tool = BUSINESS_TOOLS[toolId];
  const tierLevels: Record<BusinessTier, number> = {
    'basic': 1,
    'pro': 2,
    'pro-plus': 3
  };
  
  return tierLevels[user.businessTier] >= tierLevels[tool.tier];
};

// Ubuntu Community Benefits (FREE)
export const getUbuntuCommunityBenefits = (tier: UbuntuTier): string[] => {
  const benefits = [
    'Ubuntu Community Access',
    'Peer-to-Peer Networking',
    'Business Opportunity Sharing',
    'Community Support System',
    'Cultural Values Integration'
  ];
  
  if (tier === 'ubuntu-champion') {
    benefits.push(
      'Mentorship Program Access',
      'Community Leadership Role',
      'Priority Community Support',
      'Ubuntu Success Stories Feature'
    );
  }
  
  return benefits;
};

// Business Subscription Benefits (PAID)
export const getBusinessSubscriptionBenefits = (tier: BusinessTier): string[] => {
  const benefits = [];
  
  if (tier === 'basic') {
    benefits.push(
      'Advanced Analytics Dashboard',
      'Basic CRM Tools',
      'Email Marketing Integration',
      'Performance Reporting'
    );
  }
  
  if (tier === 'pro' || tier === 'pro-plus') {
    benefits.push(
      'Marketing Automation Suite',
      'Advanced Affiliate Management',
      'Workflow Automation',
      'Priority Customer Support'
    );
  }
  
  if (tier === 'pro-plus') {
    benefits.push(
      'Third-Party Integrations',
      'Custom Business Solutions',
      'Dedicated Account Manager',
      'Advanced API Access'
    );
  }
  
  return benefits;
};

// Ubuntu Philosophy Messages
export const UBUNTU_MESSAGES = {
  welcome: "Sawubona! Welcome to Ubuntu NTheemba - where we grow together",
  philosophy: "Ubuntu: I am because we are. Your success is our success.",
  community: "In the spirit of Ubuntu, let's build each other up",
  support: "Together we are stronger. Together we prosper.",
  growth: "Growing individually while lifting the entire community",
  unity: "One Africa, One Dream, One Success Story at a time",
  free_community: "Ubuntu community is free for all - business tools are subscription-based",
  upgrade_message: "Upgrade to unlock powerful business tools while keeping your community access"
};

// Ubuntu Pricing Structure
export const UBUNTU_PRICING = {
  community: {
    price: 0,
    currency: 'ZMW',
    description: 'Forever free Ubuntu community access'
  },
  business: {
    basic: {
      msme: { price: 199, currency: 'ZMW', description: 'Essential MSME business tools' },
      affiliate: { price: 99, currency: 'ZMW', description: 'Core affiliate marketing tools' }
    },
    pro: {
      msme: { price: 399, currency: 'ZMW', description: 'Advanced MSME automation & analytics' },
      affiliate: { price: 199, currency: 'ZMW', description: 'Professional affiliate management' }
    },
    'pro-plus': {
      msme: { price: 699, currency: 'ZMW', description: 'Enterprise MSME solutions' },
      affiliate: { price: 399, currency: 'ZMW', description: 'Premium affiliate platform' }
    }
  }
};

// Hook for Ubuntu system
export const useUbuntuSystem = (user: UbuntuUser) => {
  const ubuntuScore = calculateUbuntuScore(user);
  const nextTier = getNextUbuntuTier(user.ubuntuTier, ubuntuScore);
  
  return {
    // Free community features
    ubuntuScore,
    nextTier,
    communityBenefits: getUbuntuCommunityBenefits(user.ubuntuTier),
    availableActions: Object.values(FREE_UBUNTU_FEATURES),
    
    // Paid business features
    businessToolAccess: user.businessSubscriptionActive,
    businessBenefits: user.businessSubscriptionActive 
      ? getBusinessSubscriptionBenefits(user.businessTier) 
      : [],
    hasToolAccess: (toolId: keyof typeof BUSINESS_TOOLS) => hasBusinessToolAccess(user, toolId),
    
    // Ubuntu philosophy & messaging
    philosophy: UBUNTU_MESSAGES,
    pricing: UBUNTU_PRICING,
    
    // User status
    isFreeTier: !user.businessSubscriptionActive,
    canUpgrade: !user.businessSubscriptionActive || user.businessTier !== 'pro-plus'
  };
};

export default {
  FREE_UBUNTU_FEATURES,
  BUSINESS_TOOLS,
  UBUNTU_MESSAGES,
  UBUNTU_PRICING,
  calculateUbuntuScore,
  getNextUbuntuTier,
  hasBusinessToolAccess,
  getUbuntuCommunityBenefits,
  getBusinessSubscriptionBenefits,
  useUbuntuSystem
};

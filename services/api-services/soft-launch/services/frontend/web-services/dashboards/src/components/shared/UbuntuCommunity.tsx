import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { 
  Heart, 
  Users, 
  Handshake, 
  Trophy, 
  Target,
  TrendingUp,
  Globe,
  Star,
  Gift,
  ArrowRight,
  Crown,
  Zap
} from "lucide-react";

const UbuntuCommunity = () => {
  const communityStats = {
    totalMembers: 2847,
    activeMSMEs: 1205,
    activeAffiliates: 1642,
    crossPromotions: 5623,
    totalEarnings: 156750.50,
    helpedBusinesses: 892
  };

  const recentActivities = [
    { id: 1, type: 'promotion', user: 'Sarah K.', action: 'promoted Kambeshi Crafts', time: '2 min ago', points: 25 },
    { id: 2, type: 'milestone', user: 'John M.', action: 'reached 100 cross-promotions', time: '15 min ago', points: 100 },
    { id: 3, type: 'join', user: 'Mwanza Textiles', action: 'joined Ubuntu Community', time: '1 hour ago', points: 50 }
  ];

  const topContributors = [
    { name: 'Chipo Musonda', business: 'Lusaka Fashion Hub', points: 2450, level: 'Ubuntu Champion' },
    { name: 'James Banda', business: 'Affiliate Partner', points: 2180, level: 'Ubuntu Leader' },
    { name: 'Grace Mwale', business: 'Kitwe Crafts Co.', points: 1890, level: 'Ubuntu Ambassador' }
  ];

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4 max-w-7xl mx-auto">
      {/* Header Section */}
      <div className="text-center space-y-3 sm:space-y-4">
        <div className="flex items-center justify-center space-x-2 sm:space-x-3">
          <Heart className="w-6 h-6 sm:w-8 sm:h-8 text-orange-600" />
          <h1 className="text-2xl sm:text-3xl font-bold">Ubuntu Community</h1>
          <Heart className="w-6 h-6 sm:w-8 sm:h-8 text-red-600" />
        </div>
        <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto px-4">
          "I am because we are" - Join fellow African entrepreneurs in a spirit of mutual success, 
          unity, and shared prosperity. Together, we lift each other up.
        </p>
        <Badge className="bg-gradient-to-r from-orange-500 to-red-500 text-white px-3 py-1 sm:px-4 sm:py-2 text-sm">
          African Unity in Business
        </Badge>
      </div>

      {/* Community Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-3 sm:p-4 text-center">
            <Users className="w-6 h-6 sm:w-8 sm:h-8 mx-auto mb-2 text-blue-600" />
            <div className="text-xl sm:text-2xl font-bold">{communityStats.totalMembers.toLocaleString()}</div>
            <div className="text-xs sm:text-sm text-muted-foreground">Total Members</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-3 sm:p-4 text-center">
            <Trophy className="w-6 h-6 sm:w-8 sm:h-8 mx-auto mb-2 text-purple-600" />
            <div className="text-xl sm:text-2xl font-bold">{communityStats.activeMSMEs.toLocaleString()}</div>
            <div className="text-xs sm:text-sm text-muted-foreground">Active MSMEs</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-3 sm:p-4 text-center">
            <Target className="w-6 h-6 sm:w-8 sm:h-8 mx-auto mb-2 text-green-600" />
            <div className="text-xl sm:text-2xl font-bold">{communityStats.activeAffiliates.toLocaleString()}</div>
            <div className="text-xs sm:text-sm text-muted-foreground">Affiliates</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-3 sm:p-4 text-center">
            <Handshake className="w-6 h-6 sm:w-8 sm:h-8 mx-auto mb-2 text-orange-600" />
            <div className="text-xl sm:text-2xl font-bold">{communityStats.crossPromotions.toLocaleString()}</div>
            <div className="text-xs sm:text-sm text-muted-foreground">Cross-Promotions</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-3 sm:p-4 text-center">
            <Gift className="w-6 h-6 sm:w-8 sm:h-8 mx-auto mb-2 text-red-600" />
            <div className="text-xl sm:text-2xl font-bold">ZMW {communityStats.totalEarnings.toLocaleString()}</div>
            <div className="text-xs sm:text-sm text-muted-foreground">Ubuntu Earnings</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-3 sm:p-4 text-center">
            <TrendingUp className="w-6 h-6 sm:w-8 sm:h-8 mx-auto mb-2 text-yellow-600" />
            <div className="text-xl sm:text-2xl font-bold">{communityStats.helpedBusinesses}</div>
            <div className="text-xs sm:text-sm text-muted-foreground">Businesses Helped</div>
          </CardContent>
        </Card>
      </div>

      {/* Ubuntu Principles */}
      <Card className="bg-gradient-to-r from-orange-50 to-red-50 border-2 border-orange-200">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
            <Globe className="w-5 h-5 sm:w-6 sm:h-6 text-orange-600" />
            <span>Ubuntu Principles</span>
          </CardTitle>
          <CardDescription className="text-sm sm:text-base">
            The foundation of our community - rooted in African philosophy
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            <div className="space-y-3 sm:space-y-4">
              <div className="flex items-start space-x-3">
                <Heart className="w-4 h-4 sm:w-5 sm:h-5 text-red-500 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-sm sm:text-base">Humanity & Compassion</h4>
                  <p className="text-xs sm:text-sm text-muted-foreground">We see the humanity in every business owner and support each other with genuine care.</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <Handshake className="w-4 h-4 sm:w-5 sm:h-5 text-orange-500 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-sm sm:text-base">Mutual Support</h4>
                  <p className="text-xs sm:text-sm text-muted-foreground">When one succeeds, we all succeed. We actively promote and support fellow businesses.</p>
                </div>
              </div>
            </div>
            <div className="space-y-3 sm:space-y-4">
              <div className="flex items-start space-x-3">
                <Users className="w-4 h-4 sm:w-5 sm:h-5 text-blue-500 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-sm sm:text-base">Community First</h4>
                  <p className="text-xs sm:text-sm text-muted-foreground">Individual success is meaningful only when it contributes to community prosperity.</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <Star className="w-4 h-4 sm:w-5 sm:h-5 text-yellow-500 mt-1 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-sm sm:text-base">Shared Wisdom</h4>
                  <p className="text-xs sm:text-sm text-muted-foreground">We share knowledge, experiences, and resources to help everyone grow.</p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Recent Community Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
              <Zap className="w-4 h-4 sm:w-5 sm:h-5 text-blue-600" />
              <span>Recent Community Activity</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 sm:space-y-4">
              {recentActivities.map((activity) => (
                <div key={activity.id} className="flex items-center justify-between p-2 sm:p-3 border rounded-lg hover:shadow-sm transition-shadow">
                  <div className="flex items-center space-x-2 sm:space-x-3 min-w-0 flex-1">
                    <div className={`p-1.5 sm:p-2 rounded-full flex-shrink-0 ${
                      activity.type === 'promotion' ? 'bg-orange-100' :
                      activity.type === 'milestone' ? 'bg-yellow-100' : 'bg-green-100'
                    }`}>
                      {activity.type === 'promotion' ? <Handshake className="w-3 h-3 sm:w-4 sm:h-4 text-orange-600" /> :
                       activity.type === 'milestone' ? <Trophy className="w-3 h-3 sm:w-4 sm:h-4 text-yellow-600" /> :
                       <Users className="w-3 h-3 sm:w-4 sm:h-4 text-green-600" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs sm:text-sm font-medium truncate">{activity.user} {activity.action}</p>
                      <p className="text-xs text-muted-foreground">{activity.time}</p>
                    </div>
                  </div>
                  <Badge variant="secondary" className="text-xs ml-2 flex-shrink-0">+{activity.points} pts</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Contributors */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2 text-lg sm:text-xl">
              <Crown className="w-4 h-4 sm:w-5 sm:h-5 text-yellow-600" />
              <span>Ubuntu Champions</span>
            </CardTitle>
            <CardDescription className="text-sm">
              Top contributors spreading the Ubuntu spirit
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 sm:space-y-4">
              {topContributors.map((contributor, index) => (
                <div key={index} className="flex items-center justify-between p-2 sm:p-3 border rounded-lg hover:shadow-sm transition-shadow">
                  <div className="flex items-center space-x-2 sm:space-x-3 min-w-0 flex-1">
                    <div className={`w-6 h-6 sm:w-8 sm:h-8 rounded-full flex items-center justify-center font-bold text-xs sm:text-sm flex-shrink-0 ${
                      index === 0 ? 'bg-yellow-100 text-yellow-800' :
                      index === 1 ? 'bg-gray-100 text-gray-800' :
                      'bg-orange-100 text-orange-800'
                    }`}>
                      {index + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm sm:text-base truncate">{contributor.name}</p>
                      <p className="text-xs sm:text-sm text-muted-foreground truncate">{contributor.business}</p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="font-bold text-sm sm:text-base">{contributor.points.toLocaleString()}</div>
                    <Badge variant="outline" className="text-xs">{contributor.level}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Join Ubuntu Actions */}
      <Card className="bg-gradient-to-r from-orange-600 to-red-600 text-white">
        <CardContent className="p-4 sm:p-6">
          <div className="text-center space-y-3 sm:space-y-4">
            <h3 className="text-xl sm:text-2xl font-bold">Ready to Embrace Ubuntu?</h3>
            <p className="text-orange-100 text-sm sm:text-base px-2">
              Join thousands of African entrepreneurs who are building success together
            </p>
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
              <Button className="bg-white text-orange-600 hover:bg-orange-50 text-sm sm:text-base py-2 sm:py-3">
                <Heart className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
                Join Ubuntu Community
              </Button>
              <Button variant="outline" className="border-white text-white hover:bg-white hover:text-orange-600 text-sm sm:text-base py-2 sm:py-3">
                <Handshake className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
                Start Cross-Promoting
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default UbuntuCommunity;

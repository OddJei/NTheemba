import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { 
  Plus, 
  Search, 
  Calendar,
  Share2,
  Eye,
  Edit,
  Trash2,
  Facebook,
  MessageCircle,
  Instagram,
  Clock,
  Users,
  TrendingUp
} from "lucide-react";

const MSMECampaigns = () => {
  const [activeTab, setActiveTab] = useState<'active' | 'scheduled' | 'templates'>('active');

  const activeCampaigns = [
    {
      id: 1,
      name: "Diwali Special Offer",
      type: "Seasonal",
      status: "Active",
      startDate: "2024-10-15",
      endDate: "2024-11-15",
      reach: 12500,
      engagement: "8.5%",
      sales: "ZMW 45,600"
    },
    {
      id: 2,
      name: "New Cotton Collection",
      type: "Product Launch",
      status: "Active",
      startDate: "2024-10-01",
      endDate: "2024-10-31",
      reach: 8200,
      engagement: "12.3%",
      sales: "ZMW 28,900"
    }
  ];

  const campaignTemplates = [
    {
      id: 1,
      name: "Festival Sale",
      description: "Perfect for seasonal promotions and festivals",
      platforms: ["Facebook", "WhatsApp", "Instagram"],
      preview: "🎉 Special Festival Offer! Get up to 50% off on all products..."
    },
    {
      id: 2,
      name: "Product Launch",
      description: "Introduce new products to your customers",
      platforms: ["Facebook", "Instagram"],
      preview: "🆕 Introducing our latest collection! Made with premium quality..."
    },
    {
      id: 3,
      name: "Customer Testimonial",
      description: "Share customer reviews and build trust",
      platforms: ["Facebook", "Instagram", "WhatsApp"],
      preview: "⭐ Here's what our customers are saying about us..."
    },
    {
      id: 4,
      name: "Limited Time Offer",
      description: "Create urgency with time-limited deals",
      platforms: ["WhatsApp", "Facebook"],
      preview: "⏰ Hurry! Limited time offer ending soon. Get your favorites now..."
    }
  ];

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case 'Facebook': return <Facebook className="w-4 h-4" />;
      case 'WhatsApp': return <MessageCircle className="w-4 h-4" />;
      case 'Instagram': return <Instagram className="w-4 h-4" />;
      default: return <Share2 className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold">Campaign Tools</h1>
          <p className="text-muted-foreground">Create and manage your marketing campaigns</p>
        </div>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          Create Campaign
        </Button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Campaigns</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">2</div>
            <p className="text-xs text-muted-foreground">Running successfully</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Reach</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">20.7K</div>
            <p className="text-xs text-muted-foreground">People reached</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Engagement</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">10.4%</div>
            <p className="text-xs text-muted-foreground">Above industry avg</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Campaign Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">ZMW 74.5K</div>
            <p className="text-xs text-muted-foreground">This month</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-muted p-1 rounded-lg w-fit">
        <Button
          variant={activeTab === 'active' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('active')}
        >
          Active Campaigns
        </Button>
        <Button
          variant={activeTab === 'scheduled' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('scheduled')}
        >
          Scheduled
        </Button>
        <Button
          variant={activeTab === 'templates' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('templates')}
        >
          Templates
        </Button>
      </div>

      {/* Active Campaigns */}
      {activeTab === 'active' && (
        <div className="space-y-4">
          <div className="flex items-center space-x-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search campaigns..." className="pl-10" />
            </div>
          </div>

          <div className="grid gap-4">
            {activeCampaigns.map((campaign) => (
              <Card key={campaign.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center space-x-2">
                        <span>{campaign.name}</span>
                        <Badge variant="secondary">{campaign.type}</Badge>
                        <Badge className="bg-green-100 text-green-800">{campaign.status}</Badge>
                      </CardTitle>
                      <CardDescription className="flex items-center space-x-4 mt-1">
                        <span className="flex items-center">
                          <Calendar className="w-4 h-4 mr-1" />
                          {campaign.startDate} - {campaign.endDate}
                        </span>
                      </CardDescription>
                    </div>
                    <div className="flex space-x-2">
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="flex items-center justify-center space-x-1 mb-1">
                        <Users className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">Reach</span>
                      </div>
                      <div className="text-xl font-bold">{campaign.reach.toLocaleString()}</div>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center space-x-1 mb-1">
                        <TrendingUp className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">Engagement</span>
                      </div>
                      <div className="text-xl font-bold">{campaign.engagement}</div>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center space-x-1 mb-1">
                        <span className="text-sm text-muted-foreground">Revenue</span>
                      </div>
                      <div className="text-xl font-bold text-green-600">{campaign.sales}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Scheduled Campaigns */}
      {activeTab === 'scheduled' && (
        <Card>
          <CardHeader>
            <CardTitle>Scheduled Campaigns</CardTitle>
            <CardDescription>Campaigns set to run in the future</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center py-8">
              <Clock className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No scheduled campaigns</p>
              <Button className="mt-4">Schedule Your First Campaign</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Campaign Templates */}
      {activeTab === 'templates' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-muted-foreground">Choose from our proven campaign templates</p>
            <Button variant="outline">
              <Plus className="w-4 h-4 mr-2" />
              Create Custom Template
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {campaignTemplates.map((template) => (
              <Card key={template.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{template.name}</CardTitle>
                  <CardDescription>{template.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <p className="text-sm font-medium mb-2">Supported Platforms:</p>
                    <div className="flex space-x-2">
                      {template.platforms.map((platform) => (
                        <Badge key={platform} variant="outline" className="flex items-center space-x-1">
                          {getPlatformIcon(platform)}
                          <span>{platform}</span>
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <p className="text-sm font-medium mb-2">Preview:</p>
                    <div className="bg-muted p-3 rounded-md text-sm">
                      {template.preview}
                    </div>
                  </div>
                  
                  <div className="flex space-x-2">
                    <Button className="flex-1">Use Template</Button>
                    <Button variant="outline">
                      <Eye className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MSMECampaigns;
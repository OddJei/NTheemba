import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  MessageSquare, 
  Bot, 
  Smartphone, 
  Users, 
  TrendingUp, 
  Clock, 
  CheckCircle, 
  RefreshCw, 
  Upload,
  BarChart3,
  HelpCircle,
  Edit3,
  Globe,
  Activity,
  Plug
} from 'lucide-react';

const MSMEBranding = () => {
  const [whatsAppConnected, setWhatsAppConnected] = useState(false);
  const [botEnabled, setBotEnabled] = useState(true);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const id = window.location.hash.replace('#', '');
      const el = document.getElementById(id);
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
        (el as HTMLElement).focus?.();
      }
    }
  }, []);

  // Mock bot performance data
  const botStats = {
    totalMessages: 1247,
    responseRate: 98.5,
    avgResponseTime: 2.3,
    customerSatisfaction: 4.7,
    conversionsFromBot: 156,
    activeSessions: 23,
    botUptime: 99.2,
    recoveredSessions: 12
  };

  const recentBotActivity = [
    { type: 'order', message: 'New order placed via NTheemba Bot', time: '2 mins ago', status: 'success' },
    { type: 'faq', message: 'Customer asked about delivery times', time: '5 mins ago', status: 'handled' },
    { type: 'catalog', message: 'Product catalog viewed 15 times', time: '10 mins ago', status: 'info' },
    { type: 'session', message: 'Session recovery completed for 3 users', time: '15 mins ago', status: 'recovery' }
  ];

  const commonQueries = [
    { query: 'Do you deliver?', count: 45, handled: 'auto' },
    { query: 'What are your business hours?', count: 32, handled: 'needs_info' },
    { query: 'How do I place an order?', count: 28, handled: 'auto' },
    { query: 'What payment methods do you accept?', count: 24, handled: 'needs_info' },
  ];

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">NTheemba Bot & Branding</h1>
          <p className="text-muted-foreground text-sm sm:text-base">
            Connect to the shared NTheemba Bot system and manage your business presence
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button variant="outline" className="w-full sm:w-auto">
            <Upload className="w-4 h-4 mr-2" />
            Upload Logo
          </Button>
          <Button className="w-full sm:w-auto">
            <RefreshCw className="w-4 h-4 mr-2" />
            Sync Business Info
          </Button>
        </div>
      </div>

      <Tabs defaultValue="bot-performance" className="w-full">
        <TabsList className="grid w-full grid-cols-1 sm:grid-cols-3">
          <TabsTrigger value="bot-performance">Bot Performance</TabsTrigger>
          <TabsTrigger value="connection">Connection Setup</TabsTrigger>
          <TabsTrigger value="business-info">Business Info</TabsTrigger>
        </TabsList>

        {/* Bot Performance Tab */}
        <TabsContent value="bot-performance" className="space-y-4">
          {/* Connection Status */}
          <Alert>
            <Plug className="h-4 w-4" />
            <AlertDescription>
              <strong>Shared NTheemba Bot System</strong> - Your business is connected to our intelligent bot that serves multiple businesses with standardized features.
            </AlertDescription>
          </Alert>

          {/* Bot Status */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="w-5 h-5" />
                Your Bot Performance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-medium">Connected</span>
                  </div>
                  <Badge variant="secondary" className="bg-green-100 text-green-800">
                    {botStats.botUptime}% Uptime
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-blue-600" />
                    <span className="text-sm font-medium">Active Chats</span>
                  </div>
                  <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                    {botStats.activeSessions}
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-orange-600" />
                    <span className="text-sm font-medium">Response Time</span>
                  </div>
                  <Badge variant="secondary" className="bg-orange-100 text-orange-800">
                    {botStats.avgResponseTime}s
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-purple-600" />
                    <span className="text-sm font-medium">Conversions</span>
                  </div>
                  <Badge variant="secondary" className="bg-purple-100 text-purple-800">
                    {botStats.conversionsFromBot}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Performance Metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <BarChart3 className="w-5 h-5" />
                  Your Business Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold text-green-600">{botStats.totalMessages}</div>
                    <div className="text-xs text-muted-foreground">Messages Handled</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">{botStats.conversionsFromBot}</div>
                    <div className="text-xs text-muted-foreground">Orders via Bot</div>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Customer Satisfaction</span>
                    <span className="font-medium">{botStats.customerSatisfaction}/5.0</span>
                  </div>
                  <Progress value={(botStats.customerSatisfaction / 5) * 100} className="h-2" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Activity className="w-5 h-5" />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {recentBotActivity.map((activity, index) => (
                    <div key={index} className="flex items-start gap-3 p-2 rounded-lg bg-gray-50">
                      <div className={`w-2 h-2 rounded-full mt-2 ${
                        activity.status === 'success' ? 'bg-green-500' :
                        activity.status === 'handled' ? 'bg-blue-500' :
                        activity.status === 'recovery' ? 'bg-purple-500' :
                        'bg-gray-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium">{activity.message}</p>
                        <p className="text-xs text-muted-foreground">{activity.time}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Common Customer Queries */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HelpCircle className="w-5 h-5" />
                Common Customer Queries
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {commonQueries.map((query, index) => (
                  <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex-1">
                      <p className="font-medium text-sm">{query.query}</p>
                      <p className="text-xs text-muted-foreground">Asked {query.count} times</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant={query.handled === 'auto' ? 'secondary' : 'outline'}
                        className={query.handled === 'auto' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}
                      >
                        {query.handled === 'auto' ? 'Auto-handled' : 'Needs Info'}
                      </Badge>
                      {query.handled === 'needs_info' && (
                        <Button size="sm" variant="outline">
                          <Edit3 className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Connection Setup Tab */}
  <TabsContent value="connection" className="space-y-4" id="connection">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5" />
                Connect to NTheemba Bot
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                  <Smartphone className="h-4 w-4" />
                <AlertDescription>
                  Connect your WhatsApp Business number to the shared NTheemba Bot system. No setup required - just plug and play!
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="space-y-1">
                    <h3 className="font-medium">WhatsApp Business Number</h3>
                    <p className="text-sm text-muted-foreground">
                      {whatsAppConnected ? 'Connected: +260 97 123 4567' : 'Not connected to NTheemba Bot'}
                    </p>
                  </div>
                  <Button 
                    variant={whatsAppConnected ? "outline" : "default"}
                    onClick={() => setWhatsAppConnected(!whatsAppConnected)}
                  >
                    {whatsAppConnected ? 'Disconnect' : 'Connect to Bot'}
                  </Button>
                </div>

                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Bot className="w-4 h-4" />
                      <span className="font-medium">Enable Bot for Your Business</span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Allow customers to interact with the NTheemba Bot on your WhatsApp
                    </p>
                  </div>
                  <Switch 
                    checked={botEnabled} 
                    onCheckedChange={setBotEnabled}
                    disabled={!whatsAppConnected} 
                  />
                </div>

                {whatsAppConnected && (
                  <div className="p-4 bg-green-50 rounded-lg">
                    <h3 className="font-medium text-green-800 mb-2">What happens next?</h3>
                    <ul className="text-sm text-green-700 space-y-1">
                      <li>• Customers can message your WhatsApp Business number</li>
                      <li>• NTheemba Bot handles common questions automatically</li>
                      <li>• Orders and complex queries are forwarded to you</li>
                      <li>• All conversations are tracked in your dashboard</li>
                    </ul>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Business Information Tab */}
        <TabsContent value="business-info" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="w-5 h-5" />
                Business Information for Bot
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert>
                <AlertDescription>
                  Provide basic business information so the NTheemba Bot can help your customers effectively.
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Business Name</label>
                  <Input placeholder="Your business name as customers know it" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Business Hours</label>
                  <Input placeholder="e.g., Monday - Friday, 8AM - 6PM" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Delivery Information</label>
                  <Input placeholder="e.g., We deliver within Lusaka CBD" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Payment Methods</label>
                  <Input placeholder="e.g., Mobile Money, Cash, Bank Transfer" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Contact Information</label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <Input placeholder="Phone number" />
                    <Input placeholder="Email (optional)" />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Additional Information</label>
                  <Textarea 
                    placeholder="Any other details customers frequently ask about..." 
                    rows={3}
                  />
                </div>

                <Button className="w-full sm:w-auto">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Update Bot Information
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MSMEBranding;
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { 
  Shield, 
  Key, 
  Lock,
  Smartphone,
  AlertTriangle,
  CheckCircle,
  Clock,
  Activity,
  Globe,
  UserCheck,
  FileText,
  Download,
  Eye,
  EyeOff
} from 'lucide-react';

const AffiliateSecurity = () => {
  const [showApiKey, setShowApiKey] = useState(false);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [loginAlerts, setLoginAlerts] = useState(true);

  const securityLogs = [
    {
      id: 1,
      type: 'login',
      action: 'Successful Login',
      location: 'Johannesburg, South Africa',
      device: 'Chrome on Windows',
      time: '2 hours ago',
      status: 'success'
    },
    {
      id: 2,
      type: 'security',
      action: 'Password Changed',
      location: 'Johannesburg, South Africa',
      device: 'Chrome on Windows',
      time: '1 day ago',
      status: 'success'
    },
    {
      id: 3,
      type: 'api',
      action: 'API Key Generated',
      location: 'Cape Town, South Africa',
      device: 'Mobile App',
      time: '3 days ago',
      status: 'success'
    },
    {
      id: 4,
      type: 'warning',
      action: 'Failed Login Attempt',
      location: 'Unknown Location',
      device: 'Unknown Device',
      time: '1 week ago',
      status: 'warning'
    }
  ];

  const complianceItems = [
    {
      title: 'Data Protection (POPIA)',
      status: 'compliant',
      description: 'Personal data handling complies with POPIA regulations',
      lastReview: '2024-01-15'
    },
    {
      title: 'Payment Security (PCI DSS)',
      status: 'compliant',
      description: 'Payment processing meets PCI DSS standards',
      lastReview: '2024-01-10'
    },
    {
      title: 'API Security Standards',
      status: 'compliant',
      description: 'API endpoints secured with industry standards',
      lastReview: '2024-01-20'
    },
    {
      title: 'Affiliate Terms Agreement',
      status: 'pending',
      description: 'Updated terms require acknowledgment',
      lastReview: '2024-01-01'
    }
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      case 'compliant':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-orange-500" />;
      default:
        return <Activity className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      'success': 'default',
      'warning': 'destructive',
      'compliant': 'default',
      'pending': 'secondary'
    };
    
    return (
      <Badge variant={variants[status] || 'outline'}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Security Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Shield className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Security Score</p>
                <p className="text-2xl font-bold text-green-600">95/100</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Key className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Active Sessions</p>
                <p className="text-2xl font-bold">3</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Lock className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">2FA Status</p>
                <p className="text-2xl font-bold text-green-600">Active</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-orange-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Alerts</p>
                <p className="text-2xl font-bold">1</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="security" className="space-y-6">
        <TabsList>
          <TabsTrigger value="security">Security Settings</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
          <TabsTrigger value="logs">Activity Logs</TabsTrigger>
          <TabsTrigger value="api">API Access</TabsTrigger>
        </TabsList>

        <TabsContent value="security" className="space-y-6">
          {/* Password & Authentication */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Lock className="w-5 h-5" />
                <span>Password & Authentication</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Two-Factor Authentication</h4>
                    <p className="text-sm text-gray-600">Add an extra layer of security to your account</p>
                  </div>
                  <Switch 
                    checked={twoFactorEnabled} 
                    onCheckedChange={setTwoFactorEnabled}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Email Login Alerts</h4>
                    <p className="text-sm text-gray-600">Get notified of login attempts</p>
                  </div>
                  <Switch 
                    checked={emailNotifications} 
                    onCheckedChange={setEmailNotifications}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Suspicious Activity Alerts</h4>
                    <p className="text-sm text-gray-600">Alert for unusual account activity</p>
                  </div>
                  <Switch 
                    checked={loginAlerts} 
                    onCheckedChange={setLoginAlerts}
                  />
                </div>
              </div>

              <div className="pt-4 border-t">
                <Button className="mr-3">Change Password</Button>
                <Button variant="outline">Backup Codes</Button>
              </div>
            </CardContent>
          </Card>

          {/* Active Sessions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Globe className="w-5 h-5" />
                <span>Active Sessions</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">Current Session</p>
                    <p className="text-sm text-gray-600">Chrome on Windows • Johannesburg, SA</p>
                    <p className="text-xs text-gray-500">Last active: Now</p>
                  </div>
                  <Badge variant="default">Current</Badge>
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">Mobile App</p>
                    <p className="text-sm text-gray-600">iOS App • Cape Town, SA</p>
                    <p className="text-xs text-gray-500">Last active: 2 hours ago</p>
                  </div>
                  <Button variant="outline" size="sm">Revoke</Button>
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">Firefox Browser</p>
                    <p className="text-sm text-gray-600">Firefox on macOS • Durban, SA</p>
                    <p className="text-xs text-gray-500">Last active: 1 day ago</p>
                  </div>
                  <Button variant="outline" size="sm">Revoke</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="compliance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <UserCheck className="w-5 h-5" />
                <span>Compliance Status</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {complianceItems.map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(item.status)}
                      <div>
                        <p className="font-medium">{item.title}</p>
                        <p className="text-sm text-gray-600">{item.description}</p>
                        <p className="text-xs text-gray-500">Last reviewed: {item.lastReview}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      {getStatusBadge(item.status)}
                      {item.status === 'pending' && (
                        <Button variant="outline" size="sm">Review</Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <FileText className="w-5 h-5" />
                <span>Legal Documents</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <span>Affiliate Agreement (v2.1)</span>
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                </div>
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <span>Privacy Policy (v1.3)</span>
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                </div>
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <span>Terms of Service (v1.5)</span>
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logs" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Activity className="w-5 h-5" />
                <span>Security Activity Log</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {securityLogs.map((log) => (
                  <div key={log.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(log.status)}
                      <div>
                        <p className="font-medium">{log.action}</p>
                        <p className="text-sm text-gray-600">{log.location} • {log.device}</p>
                        <p className="text-xs text-gray-500">{log.time}</p>
                      </div>
                    </div>
                    {getStatusBadge(log.status)}
                  </div>
                ))}
              </div>
              
              <div className="pt-4 border-t flex justify-center">
                <Button variant="outline">Load More Logs</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Key className="w-5 h-5" />
                <span>API Access</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                <AlertTriangle className="w-4 h-4" />
                <AlertDescription>
                  Keep your API keys secure. Never share them in public repositories or client-side code.
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Primary API Key</label>
                  <div className="flex space-x-2">
                    <Input 
                      type={showApiKey ? "text" : "password"}
                      value="ntb_live_sk_1234567890abcdef"
                      readOnly
                      className="font-mono"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </Button>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">Created: Jan 15, 2024 • Last used: 2 hours ago</p>
                </div>

                <div className="flex space-x-3">
                  <Button variant="outline">Regenerate Key</Button>
                  <Button variant="outline">Create New Key</Button>
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-3">API Usage Statistics</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 border rounded-lg">
                    <p className="text-sm text-gray-600">Requests Today</p>
                    <p className="text-2xl font-bold">1,247</p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <p className="text-sm text-gray-600">Rate Limit</p>
                    <p className="text-2xl font-bold">5,000/hour</p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <p className="text-sm text-gray-600">Success Rate</p>
                    <p className="text-2xl font-bold text-green-600">99.8%</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AffiliateSecurity;

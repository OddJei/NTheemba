import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { 
  Bell, 
  Mail, 
  MessageSquare, 
  Smartphone,
  DollarSign,
  TrendingUp,
  Users,
  Gift,
  AlertCircle,
  CheckCircle,
  Clock,
  Star,
  Target,
  Zap,
  Settings,
  Filter,
  Search,
  Trash2,
  Eye,
  EyeOff,
  Volume2,
  VolumeX,
  Calendar,
  Download,
  RefreshCw,
  Send,
  Archive,
  Flag,
  Info
} from 'lucide-react';

const AffiliateNotifications = () => {
  const [notificationFilter, setNotificationFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNotifications, setSelectedNotifications] = useState<number[]>([]);

  // Mock notification data
  const notificationSettings = {
    email: {
      earnings: true,
      payouts: true,
      campaigns: false,
      system: true,
      marketing: false
    },
    sms: {
      earnings: false,
      payouts: true,
      campaigns: false,
      system: false,
      marketing: false
    },
    push: {
      earnings: true,
      payouts: true,
      campaigns: true,
      system: true,
      marketing: true
    },
    inApp: {
      earnings: true,
      payouts: true,
      campaigns: true,
      system: true,
      marketing: true
    }
  };

  const notifications = [
    {
      id: 1,
      type: 'earnings',
      title: 'New Commission Earned',
      message: 'You earned ZMW 125.50 commission from John Doe\'s purchase',
      timestamp: '2025-09-01T10:30:00Z',
      read: false,
      priority: 'high',
      category: 'financial',
      action: { label: 'View Earnings', url: '/affiliate/earnings' }
    },
    {
      id: 2,
      type: 'payout',
      title: 'Payout Processed',
      message: 'Your payout of ZMW 890.50 has been successfully processed to MTN Mobile Money',
      timestamp: '2025-09-01T09:15:00Z',
      read: true,
      priority: 'high',
      category: 'financial',
      action: { label: 'View Payout', url: '/affiliate/payouts' }
    },
    {
      id: 3,
      type: 'campaign',
      title: 'New Campaign Available',
      message: 'A new high-converting campaign "Summer Sale 2025" is now available',
      timestamp: '2025-09-01T08:00:00Z',
      read: false,
      priority: 'medium',
      category: 'opportunity',
      action: { label: 'View Campaign', url: '/affiliate/campaigns' }
    },
    {
      id: 4,
      type: 'achievement',
      title: 'Tier Upgrade!',
      message: 'Congratulations! You\'ve been upgraded to Gold tier with 10% commission rate',
      timestamp: '2025-08-31T16:45:00Z',
      read: false,
      priority: 'high',
      category: 'achievement',
      action: { label: 'View Tiers', url: '/affiliate/earnings?tab=tiers' }
    },
    {
      id: 5,
      type: 'system',
      title: 'System Maintenance',
      message: 'Scheduled maintenance will occur on Sept 5, 2025 from 2:00-4:00 AM UTC',
      timestamp: '2025-08-31T14:20:00Z',
      read: true,
      priority: 'low',
      category: 'system',
      action: null
    },
    {
      id: 6,
      type: 'referral',
      title: 'New Referral Signup',
      message: 'Sarah Smith signed up using your referral link REF-2025-002',
      timestamp: '2025-08-31T12:10:00Z',
      read: false,
      priority: 'medium',
      category: 'growth',
      action: { label: 'View Referrals', url: '/affiliate/dashboard' }
    },
    {
      id: 7,
      type: 'marketing',
      title: 'New Marketing Materials',
      message: 'Fresh banners and promotional content are now available for download',
      timestamp: '2025-08-30T15:30:00Z',
      read: true,
      priority: 'low',
      category: 'resources',
      action: { label: 'Download Assets', url: '/affiliate/content' }
    },
    {
      id: 8,
      type: 'payment',
      title: 'Payment Method Verification',
      message: 'Please verify your new Airtel Money account to enable payouts',
      timestamp: '2025-08-30T11:20:00Z',
      read: false,
      priority: 'high',
      category: 'action_required',
      action: { label: 'Verify Now', url: '/affiliate/payouts?tab=methods' }
    }
  ];

  const notificationStats = {
    total: notifications.length,
    unread: notifications.filter(n => !n.read).length,
    high_priority: notifications.filter(n => n.priority === 'high').length,
    today: notifications.filter(n => {
      const today = new Date().toDateString();
      const notificationDate = new Date(n.timestamp).toDateString();
      return today === notificationDate;
    }).length
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'earnings':
        return <DollarSign className="w-5 h-5 text-green-500" />;
      case 'payout':
        return <Smartphone className="w-5 h-5 text-blue-500" />;
      case 'campaign':
        return <Target className="w-5 h-5 text-purple-500" />;
      case 'achievement':
        return <Star className="w-5 h-5 text-yellow-500" />;
      case 'system':
        return <Settings className="w-5 h-5 text-gray-500" />;
      case 'referral':
        return <Users className="w-5 h-5 text-indigo-500" />;
      case 'marketing':
        return <Gift className="w-5 h-5 text-pink-500" />;
      case 'payment':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Bell className="w-5 h-5 text-gray-500" />;
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'high':
        return <Badge className="bg-red-100 text-red-700">High</Badge>;
      case 'medium':
        return <Badge className="bg-yellow-100 text-yellow-700">Medium</Badge>;
      case 'low':
        return <Badge className="bg-gray-100 text-gray-700">Low</Badge>;
      default:
        return null;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'financial':
        return 'border-l-green-500';
      case 'opportunity':
        return 'border-l-purple-500';
      case 'achievement':
        return 'border-l-yellow-500';
      case 'system':
        return 'border-l-gray-500';
      case 'growth':
        return 'border-l-blue-500';
      case 'resources':
        return 'border-l-pink-500';
      case 'action_required':
        return 'border-l-red-500';
      default:
        return 'border-l-gray-300';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);

    if (diffInHours < 1) {
      const diffInMinutes = Math.floor(diffInHours * 60);
      return `${diffInMinutes} mins ago`;
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)} hours ago`;
    } else {
      const diffInDays = Math.floor(diffInHours / 24);
      return `${diffInDays} days ago`;
    }
  };

  const filteredNotifications = notifications.filter(notification => {
    if (notificationFilter !== 'all' && notification.type !== notificationFilter) return false;
    if (searchQuery && !notification.title.toLowerCase().includes(searchQuery.toLowerCase()) && 
        !notification.message.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const markAsRead = (id: number) => {
    // Implementation would update the notification as read
  };

  const markAllAsRead = () => {
    // Implementation would mark all notifications as read
  };

  const deleteNotification = (id: number) => {
    // Implementation would delete the notification
  };

  const toggleSelection = (id: number) => {
    setSelectedNotifications(prev => 
      prev.includes(id) 
        ? prev.filter(notifId => notifId !== id)
        : [...prev, id]
    );
  };

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Notifications</h1>
          <p className="text-muted-foreground text-sm sm:text-base">
            Stay updated with your affiliate activities and system updates
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button variant="outline" className="w-full sm:w-auto" onClick={markAllAsRead}>
            <CheckCircle className="w-4 h-4 mr-2" />
            Mark All Read
          </Button>
          <Button variant="outline" className="w-full sm:w-auto">
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </Button>
        </div>
      </div>

      {/* Notification Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total</p>
                <p className="text-2xl font-bold">{notificationStats.total}</p>
              </div>
              <Bell className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Unread</p>
                <p className="text-2xl font-bold text-red-600">{notificationStats.unread}</p>
              </div>
              <Eye className="w-8 h-8 text-red-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">High Priority</p>
                <p className="text-2xl font-bold text-yellow-600">{notificationStats.high_priority}</p>
              </div>
              <Flag className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Today</p>
                <p className="text-2xl font-bold text-green-600">{notificationStats.today}</p>
              </div>
              <Calendar className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="notifications" className="w-full">
        <TabsList className="grid w-full grid-cols-1 sm:grid-cols-2">
          <TabsTrigger value="notifications">All Notifications</TabsTrigger>
          <TabsTrigger value="settings">Notification Settings</TabsTrigger>
        </TabsList>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="space-y-4">
          {/* Filters and Search */}
          <Card>
            <CardContent className="p-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      placeholder="Search notifications..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Select value={notificationFilter} onValueChange={setNotificationFilter}>
                  <SelectTrigger className="w-full sm:w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="earnings">Earnings</SelectItem>
                    <SelectItem value="payout">Payouts</SelectItem>
                    <SelectItem value="campaign">Campaigns</SelectItem>
                    <SelectItem value="achievement">Achievements</SelectItem>
                    <SelectItem value="system">System</SelectItem>
                    <SelectItem value="referral">Referrals</SelectItem>
                    <SelectItem value="marketing">Marketing</SelectItem>
                    <SelectItem value="payment">Payments</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {selectedNotifications.length > 0 && (
                <div className="flex items-center gap-2 mt-4 p-2 bg-blue-50 rounded-lg">
                  <span className="text-sm text-blue-700">
                    {selectedNotifications.length} selected
                  </span>
                  <Button variant="ghost" size="sm">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    Mark Read
                  </Button>
                  <Button variant="ghost" size="sm">
                    <Archive className="w-4 h-4 mr-1" />
                    Archive
                  </Button>
                  <Button variant="ghost" size="sm">
                    <Trash2 className="w-4 h-4 mr-1" />
                    Delete
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Notifications List */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Recent Notifications</span>
                <Button variant="ghost" size="sm">
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {filteredNotifications.map((notification) => (
                  <div 
                    key={notification.id} 
                    className={`p-4 border-l-4 rounded-lg transition-colors hover:bg-gray-50 ${
                      getCategoryColor(notification.category)
                    } ${!notification.read ? 'bg-blue-50/30' : ''}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="flex items-center gap-2">
                          <input 
                            type="checkbox"
                            checked={selectedNotifications.includes(notification.id)}
                            onChange={() => toggleSelection(notification.id)}
                          />
                          {getNotificationIcon(notification.type)}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className={`font-medium ${!notification.read ? 'font-bold' : ''}`}>
                              {notification.title}
                            </h3>
                            {!notification.read && (
                              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                            )}
                            {getPriorityBadge(notification.priority)}
                          </div>
                          <p className="text-sm text-muted-foreground mb-2">
                            {notification.message}
                          </p>
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            <span>{formatTimestamp(notification.timestamp)}</span>
                            <span className="capitalize">{notification.category.replace('_', ' ')}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {notification.action && (
                          <Button variant="ghost" size="sm" className="text-xs">
                            {notification.action.label}
                          </Button>
                        )}
                        <div className="flex items-center gap-1">
                          {!notification.read && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => markAsRead(notification.id)}
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                          )}
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => deleteNotification(notification.id)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {filteredNotifications.length === 0 && (
                <div className="text-center py-8">
                  <Bell className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No notifications found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Email Notifications */}
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Mail className="w-5 h-5 text-blue-500" />
                    <h3 className="font-semibold">Email Notifications</h3>
                  </div>
                  <div className="space-y-3 ml-7">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Earnings & Commissions</p>
                        <p className="text-sm text-muted-foreground">New commissions and earnings updates</p>
                      </div>
                      <Switch checked={notificationSettings.email.earnings} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Payout Updates</p>
                        <p className="text-sm text-muted-foreground">Payout processing and completion</p>
                      </div>
                      <Switch checked={notificationSettings.email.payouts} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Campaign Updates</p>
                        <p className="text-sm text-muted-foreground">New campaigns and opportunities</p>
                      </div>
                      <Switch checked={notificationSettings.email.campaigns} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">System Notifications</p>
                        <p className="text-sm text-muted-foreground">Important system updates</p>
                      </div>
                      <Switch checked={notificationSettings.email.system} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Marketing Updates</p>
                        <p className="text-sm text-muted-foreground">Promotional content and tips</p>
                      </div>
                      <Switch checked={notificationSettings.email.marketing} />
                    </div>
                  </div>
                </div>

                {/* SMS Notifications */}
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <MessageSquare className="w-5 h-5 text-green-500" />
                    <h3 className="font-semibold">SMS Notifications</h3>
                  </div>
                  <div className="space-y-3 ml-7">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">High-Value Earnings</p>
                        <p className="text-sm text-muted-foreground">Commissions over ZMW 100</p>
                      </div>
                      <Switch checked={notificationSettings.sms.earnings} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Payout Confirmations</p>
                        <p className="text-sm text-muted-foreground">Successful payout notifications</p>
                      </div>
                      <Switch checked={notificationSettings.sms.payouts} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Critical System Alerts</p>
                        <p className="text-sm text-muted-foreground">Urgent system notifications</p>
                      </div>
                      <Switch checked={notificationSettings.sms.system} />
                    </div>
                  </div>
                </div>

                {/* Push Notifications */}
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Smartphone className="w-5 h-5 text-purple-500" />
                    <h3 className="font-semibold">Push Notifications</h3>
                  </div>
                  <div className="space-y-3 ml-7">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Real-time Earnings</p>
                        <p className="text-sm text-muted-foreground">Instant commission notifications</p>
                      </div>
                      <Switch checked={notificationSettings.push.earnings} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Campaign Alerts</p>
                        <p className="text-sm text-muted-foreground">New high-converting campaigns</p>
                      </div>
                      <Switch checked={notificationSettings.push.campaigns} />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Achievement Badges</p>
                        <p className="text-sm text-muted-foreground">Tier upgrades and milestones</p>
                      </div>
                      <Switch checked={notificationSettings.push.marketing} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t">
                <Button className="w-full sm:w-auto">
                  Save Notification Preferences
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Advanced Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Quiet Hours</Label>
                <div className="flex items-center gap-4">
                  <Select defaultValue="22:00">
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => (
                        <SelectItem key={i} value={`${i.toString().padStart(2, '0')}:00`}>
                          {i.toString().padStart(2, '0')}:00
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span>to</span>
                  <Select defaultValue="08:00">
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => (
                        <SelectItem key={i} value={`${i.toString().padStart(2, '0')}:00`}>
                          {i.toString().padStart(2, '0')}:00
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <p className="text-sm text-muted-foreground">
                  No notifications will be sent during these hours
                </p>
              </div>

              <div className="space-y-2">
                <Label>Notification Frequency</Label>
                <Select defaultValue="realtime">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="realtime">Real-time</SelectItem>
                    <SelectItem value="hourly">Hourly digest</SelectItem>
                    <SelectItem value="daily">Daily digest</SelectItem>
                    <SelectItem value="weekly">Weekly digest</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Language</Label>
                <Select defaultValue="en">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="fr">Français</SelectItem>
                    <SelectItem value="pt">Português</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AffiliateNotifications;

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  BarChart3, 
  LineChart,
  Activity,
  MessageSquare,
  Star,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  CheckCircle,
  Clock,
  Send,
  Bug,
  Lightbulb,
  HelpCircle,
  Zap,
  TrendingUp,
  Users,
  Target,
  Gauge
} from 'lucide-react';

const AffiliateFeedback = () => {
  const [feedbackType, setFeedbackType] = useState('');
  const [feedbackText, setFeedbackText] = useState('');
  const [rating, setRating] = useState(0);

  const performanceMetrics = [
    {
      title: 'Page Load Time',
      value: '1.2s',
      trend: 'up',
      benchmark: '< 2s',
      status: 'good'
    },
    {
      title: 'API Response Time',
      value: '250ms',
      trend: 'down',
      benchmark: '< 500ms', 
      status: 'excellent'
    },
    {
      title: 'Error Rate',
      value: '0.1%',
      trend: 'down',
      benchmark: '< 1%',
      status: 'excellent'
    },
    {
      title: 'Uptime',
      value: '99.9%',
      trend: 'stable',
      benchmark: '> 99%',
      status: 'excellent'
    }
  ];

  const userFeedback = [
    {
      id: 1,
      type: 'feature',
      rating: 5,
      title: 'Love the new dashboard!',
      comment: 'The new analytics section is exactly what I needed. Great work!',
      user: 'Sarah M.',
      date: '2024-01-20',
      status: 'resolved'
    },
    {
      id: 2,
      type: 'bug',
      rating: 3,
      title: 'Mobile view issues',
      comment: 'The earnings chart doesn\'t display properly on mobile devices.',
      user: 'David K.',
      date: '2024-01-19',
      status: 'in-progress'
    },
    {
      id: 3,
      type: 'suggestion',
      rating: 4,
      title: 'Export functionality',
      comment: 'Would be great to export campaign data to CSV format.',
      user: 'Lisa P.',
      date: '2024-01-18',
      status: 'planned'
    },
    {
      id: 4,
      type: 'bug',
      rating: 2,
      title: 'Payment delay notifications',
      comment: 'Not receiving notifications about payment delays.',
      user: 'Mike R.',
      date: '2024-01-17',
      status: 'resolved'
    }
  ];

  const systemHealth = [
    {
      service: 'API Gateway',
      status: 'healthy',
      uptime: '99.9%',
      responseTime: '120ms',
      lastIncident: '5 days ago'
    },
    {
      service: 'Database',
      status: 'healthy',
      uptime: '100%',
      responseTime: '45ms',
      lastIncident: '2 weeks ago'
    },
    {
      service: 'Payment Processing',
      status: 'healthy',
      uptime: '99.8%',
      responseTime: '890ms',
      lastIncident: '3 days ago'
    },
    {
      service: 'WhatsApp Integration',
      status: 'degraded',
      uptime: '98.5%',
      responseTime: '2.1s',
      lastIncident: '2 hours ago'
    }
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'excellent': return 'text-green-600';
      case 'good': return 'text-blue-600';
      case 'warning': return 'text-orange-600';
      case 'poor': return 'text-red-600';
      case 'healthy': return 'text-green-600';
      case 'degraded': return 'text-orange-600';
      case 'down': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      'resolved': 'default',
      'in-progress': 'secondary',
      'planned': 'outline',
      'healthy': 'default',
      'degraded': 'secondary',
      'down': 'destructive'
    };
    
    return (
      <Badge variant={variants[status] || 'outline'}>
        {status.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
      </Badge>
    );
  };

  const getFeedbackIcon = (type: string) => {
    switch (type) {
      case 'bug': return <Bug className="w-4 h-4 text-red-500" />;
      case 'feature': return <Lightbulb className="w-4 h-4 text-blue-500" />;
      case 'suggestion': return <HelpCircle className="w-4 h-4 text-purple-500" />;
      default: return <MessageSquare className="w-4 h-4 text-gray-500" />;
    }
  };

  const StarRating = ({ rating, onRatingChange, readonly = false }: {
    rating: number;
    onRatingChange?: (rating: number) => void;
    readonly?: boolean;
  }) => (
    <div className="flex space-x-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`w-5 h-5 ${
            star <= rating ? 'text-yellow-400 fill-current' : 'text-gray-300'
          } ${!readonly ? 'cursor-pointer hover:text-yellow-400' : ''}`}
          onClick={() => !readonly && onRatingChange && onRatingChange(star)}
        />
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Performance Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {performanceMetrics.map((metric, index) => (
          <Card key={index}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-2">
                <div className={`p-2 rounded-lg ${
                  metric.status === 'excellent' ? 'bg-green-100' :
                  metric.status === 'good' ? 'bg-blue-100' :
                  metric.status === 'warning' ? 'bg-orange-100' : 'bg-red-100'
                }`}>
                  <Gauge className={`w-5 h-5 ${getStatusColor(metric.status)}`} />
                </div>
                <div className={`flex items-center space-x-1 ${
                  metric.trend === 'up' ? 'text-green-600' :
                  metric.trend === 'down' ? 'text-red-600' : 'text-gray-600'
                }`}>
                  <TrendingUp className={`w-4 h-4 ${
                    metric.trend === 'down' ? 'rotate-180' : 
                    metric.trend === 'stable' ? 'rotate-90' : ''
                  }`} />
                </div>
              </div>
              <p className="text-sm text-gray-600">{metric.title}</p>
              <p className="text-2xl font-bold mb-1">{metric.value}</p>
              <p className="text-xs text-gray-500">Target: {metric.benchmark}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="performance" className="space-y-6">
        <TabsList>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="health">System Health</TabsTrigger>
          <TabsTrigger value="feedback">User Feedback</TabsTrigger>
          <TabsTrigger value="submit">Submit Feedback</TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="space-y-6">
          {/* Performance Charts */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <BarChart3 className="w-5 h-5" />
                <span>Performance Analytics</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Response Time Chart */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-3">API Response Times</h4>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Authentication</span>
                      <span className="text-sm font-medium">120ms</span>
                    </div>
                    <Progress value={24} className="h-2" />
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Campaign Data</span>
                      <span className="text-sm font-medium">340ms</span>
                    </div>
                    <Progress value={68} className="h-2" />
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Analytics</span>
                      <span className="text-sm font-medium">180ms</span>
                    </div>
                    <Progress value={36} className="h-2" />
                  </div>
                </div>

                {/* Error Rates */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-3">Error Rates (24h)</h4>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">4xx Errors</span>
                      <span className="text-sm font-medium">0.05%</span>
                    </div>
                    <Progress value={5} className="h-2" />
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm">5xx Errors</span>
                      <span className="text-sm font-medium">0.02%</span>
                    </div>
                    <Progress value={2} className="h-2" />
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Timeouts</span>
                      <span className="text-sm font-medium">0.01%</span>
                    </div>
                    <Progress value={1} className="h-2" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* User Experience Metrics */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Users className="w-5 h-5" />
                <span>User Experience Metrics</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="text-center p-4">
                  <div className="text-3xl font-bold text-blue-600 mb-2">4.6</div>
                  <div className="flex justify-center mb-2">
                    <StarRating rating={5} readonly />
                  </div>
                  <p className="text-sm text-gray-600">Average Rating</p>
                </div>
                
                <div className="text-center p-4">
                  <div className="text-3xl font-bold text-green-600 mb-2">92%</div>
                  <div className="flex justify-center mb-2">
                    <ThumbsUp className="w-6 h-6 text-green-600" />
                  </div>
                  <p className="text-sm text-gray-600">Positive Feedback</p>
                </div>
                
                <div className="text-center p-4">
                  <div className="text-3xl font-bold text-purple-600 mb-2">1.2s</div>
                  <div className="flex justify-center mb-2">
                    <Zap className="w-6 h-6 text-purple-600" />
                  </div>
                  <p className="text-sm text-gray-600">Avg. Load Time</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="health" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Activity className="w-5 h-5" />
                <span>System Health Dashboard</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {systemHealth.map((service, index) => (
                  <div key={index} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${
                        service.status === 'healthy' ? 'bg-green-500' :
                        service.status === 'degraded' ? 'bg-orange-500' : 'bg-red-500'
                      }`}></div>
                      <div>
                        <p className="font-medium">{service.service}</p>
                        <p className="text-sm text-gray-600">
                          Uptime: {service.uptime} • Response: {service.responseTime}
                        </p>
                        <p className="text-xs text-gray-500">Last incident: {service.lastIncident}</p>
                      </div>
                    </div>
                    {getStatusBadge(service.status)}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent System Events</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center space-x-3 p-3 border-l-4 border-green-500 bg-green-50">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <div>
                    <p className="text-sm font-medium">System Update Completed</p>
                    <p className="text-xs text-gray-500">Dashboard performance improved by 15% • 2 hours ago</p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-3 p-3 border-l-4 border-orange-500 bg-orange-50">
                  <AlertCircle className="w-4 h-4 text-orange-500" />
                  <div>
                    <p className="text-sm font-medium">WhatsApp API Latency</p>
                    <p className="text-xs text-gray-500">Increased response times detected • 2 hours ago</p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-3 p-3 border-l-4 border-blue-500 bg-blue-50">
                  <Activity className="w-4 h-4 text-blue-500" />
                  <div>
                    <p className="text-sm font-medium">Scheduled Maintenance</p>
                    <p className="text-xs text-gray-500">Database optimization completed • 1 day ago</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="feedback" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <MessageSquare className="w-5 h-5" />
                <span>User Feedback</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {userFeedback.map((feedback) => (
                  <div key={feedback.id} className="p-4 border rounded-lg">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        {getFeedbackIcon(feedback.type)}
                        <div>
                          <p className="font-medium">{feedback.title}</p>
                          <div className="flex items-center space-x-2 mt-1">
                            <StarRating rating={feedback.rating} readonly />
                            <span className="text-sm text-gray-500">by {feedback.user}</span>
                          </div>
                        </div>
                      </div>
                      {getStatusBadge(feedback.status)}
                    </div>
                    <p className="text-sm text-gray-700 mb-2">{feedback.comment}</p>
                    <p className="text-xs text-gray-500">{feedback.date}</p>
                  </div>
                ))}
              </div>
              
              <div className="pt-4 border-t flex justify-center">
                <Button variant="outline">Load More Feedback</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="submit" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Send className="w-5 h-5" />
                <span>Submit Feedback</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                <Lightbulb className="w-4 h-4" />
                <AlertDescription>
                  Your feedback helps us improve the platform. Share your thoughts, report bugs, or suggest new features.
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Feedback Type</label>
                  <Select value={feedbackType} onValueChange={setFeedbackType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select feedback type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bug">Bug Report</SelectItem>
                      <SelectItem value="feature">Feature Request</SelectItem>
                      <SelectItem value="suggestion">Suggestion</SelectItem>
                      <SelectItem value="general">General Feedback</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Overall Rating</label>
                  <StarRating rating={rating} onRatingChange={setRating} />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Title</label>
                  <Input placeholder="Brief description of your feedback" />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Details</label>
                  <Textarea 
                    placeholder="Please provide detailed feedback. For bugs, include steps to reproduce."
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    rows={6}
                  />
                </div>

                <div className="flex space-x-3">
                  <Button className="flex-1">
                    <Send className="w-4 h-4 mr-2" />
                    Submit Feedback
                  </Button>
                  <Button variant="outline">Save Draft</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AffiliateFeedback;

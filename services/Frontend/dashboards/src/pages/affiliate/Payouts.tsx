import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { 
  Wallet, 
  CreditCard, 
  Building2, 
  Smartphone, 
  DollarSign,
  Clock,
  CheckCircle,
  AlertCircle,
  XCircle,
  Download,
  Plus,
  Edit,
  Trash2,
  Eye,
  Calendar,
  TrendingUp,
  RefreshCw,
  Shield,
  Info,
  ArrowUpRight,
  ArrowDownRight,
  Banknote,
  Receipt,
  Settings
} from 'lucide-react';

const AffiliatePayouts = () => {
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('mobile_money');
  const [payoutAmount, setPayoutAmount] = useState('');
  const [showNewPaymentMethod, setShowNewPaymentMethod] = useState(false);

  // Mock data
  const availableBalance = 14355.58;
  const minimumPayout = 50;
  const processingFee = 2.5; // percentage

  const paymentMethods = [
    { id: 'mobile_money_1', type: 'mobile_money', label: 'MTN Mobile Money', details: '+260 97 123 4567', verified: true, default: true },
    { id: 'bank_1', type: 'bank', label: 'First National Bank', details: 'Account ending in 4567', verified: true, default: false },
    { id: 'mobile_money_2', type: 'mobile_money', label: 'Airtel Money', details: '+260 95 987 6543', verified: false, default: false },
    { id: 'crypto_1', type: 'crypto', label: 'Bitcoin Wallet', details: '3A1K...5Kp9', verified: true, default: false }
  ];

  const payoutHistory = [
    { id: 1, amount: 1250.00, method: 'MTN Mobile Money', status: 'completed', requestDate: '2025-08-28', processedDate: '2025-08-29', fees: 31.25, reference: 'PO-2025-001' },
    { id: 2, amount: 890.50, method: 'First National Bank', status: 'processing', requestDate: '2025-09-01', processedDate: null, fees: 22.26, reference: 'PO-2025-002' },
    { id: 3, amount: 567.25, method: 'MTN Mobile Money', status: 'completed', requestDate: '2025-08-25', processedDate: '2025-08-26', fees: 14.18, reference: 'PO-2025-003' },
    { id: 4, amount: 2100.00, method: 'Bitcoin Wallet', status: 'failed', requestDate: '2025-08-20', processedDate: null, fees: 0, reference: 'PO-2025-004' },
    { id: 5, amount: 445.80, method: 'Airtel Money', status: 'completed', requestDate: '2025-08-15', processedDate: '2025-08-16', fees: 11.15, reference: 'PO-2025-005' }
  ];

  const payoutStats = {
    totalPayouts: 5253.55,
    totalFees: 78.84,
    successRate: 85.2,
    averageProcessingTime: '1.2 days',
    thisMonthPayouts: 2140.50,
    lastMonthPayouts: 1890.25
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'processing':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'cancelled':
        return <AlertCircle className="w-4 h-4 text-gray-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-100 text-green-700">Completed</Badge>;
      case 'processing':
        return <Badge className="bg-yellow-100 text-yellow-700">Processing</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-700">Failed</Badge>;
      case 'cancelled':
        return <Badge className="bg-gray-100 text-gray-700">Cancelled</Badge>;
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
  };

  const getMethodIcon = (type: string) => {
    switch (type) {
      case 'mobile_money':
        return <Smartphone className="w-4 h-4" />;
      case 'bank':
        return <Building2 className="w-4 h-4" />;
      case 'crypto':
        return <Banknote className="w-4 h-4" />;
      default:
        return <Wallet className="w-4 h-4" />;
    }
  };

  const calculateNetAmount = (amount: number) => {
    const fees = (amount * processingFee) / 100;
    return amount - fees;
  };

  const canRequestPayout = () => {
    const amount = parseFloat(payoutAmount);
    return amount >= minimumPayout && amount <= availableBalance;
  };

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">Payouts & Withdrawals</h1>
          <p className="text-muted-foreground text-sm sm:text-base">
            Manage your earnings withdrawals and payment methods
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button variant="outline" className="w-full sm:w-auto">
            <Download className="w-4 h-4 mr-2" />
            Export History
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button className="w-full sm:w-auto">
                <Plus className="w-4 h-4 mr-2" />
                Request Payout
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Request Payout</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="amount">Amount (ZMW)</Label>
                  <Input
                    id="amount"
                    type="number"
                    value={payoutAmount}
                    onChange={(e) => setPayoutAmount(e.target.value)}
                    placeholder={`Min ZMW ${minimumPayout}`}
                    max={availableBalance}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Available: ZMW {availableBalance.toLocaleString()}
                  </p>
                </div>

                <div>
                  <Label>Payment Method</Label>
                  <Select value={selectedPaymentMethod} onValueChange={setSelectedPaymentMethod}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {paymentMethods.filter(method => method.verified).map(method => (
                        <SelectItem key={method.id} value={method.id}>
                          <div className="flex items-center gap-2">
                            {getMethodIcon(method.type)}
                            <span>{method.label}</span>
                            {method.default && <Badge variant="secondary" className="ml-2">Default</Badge>}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {payoutAmount && (
                  <div className="p-3 bg-gray-50 rounded-lg space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>Requested Amount:</span>
                      <span>ZMW {parseFloat(payoutAmount || '0').toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Processing Fee ({processingFee}%):</span>
                      <span>-ZMW {((parseFloat(payoutAmount || '0') * processingFee) / 100).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between font-medium border-t pt-1">
                      <span>Net Amount:</span>
                      <span>ZMW {calculateNetAmount(parseFloat(payoutAmount || '0')).toFixed(2)}</span>
                    </div>
                  </div>
                )}

                <Button 
                  className="w-full" 
                  disabled={!canRequestPayout()}
                >
                  Request Payout
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Balance Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Available Balance</p>
                <p className="text-2xl font-bold">ZMW {availableBalance.toLocaleString()}</p>
                <p className="text-xs text-green-600 flex items-center mt-1">
                  <Wallet className="w-3 h-3 mr-1" />
                  Ready for withdrawal
                </p>
              </div>
              <div className="h-12 w-12 bg-green-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">This Month</p>
                <p className="text-2xl font-bold">ZMW {payoutStats.thisMonthPayouts.toLocaleString()}</p>
                <p className="text-xs text-blue-600 flex items-center mt-1">
                  <ArrowUpRight className="w-3 h-3 mr-1" />
                  +13.2% vs last month
                </p>
              </div>
              <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Success Rate</p>
                <p className="text-2xl font-bold">{payoutStats.successRate}%</p>
                <p className="text-xs text-purple-600 flex items-center mt-1">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Above average
                </p>
              </div>
              <div className="h-12 w-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <Shield className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Avg. Processing</p>
                <p className="text-2xl font-bold">{payoutStats.averageProcessingTime}</p>
                <p className="text-xs text-orange-600 flex items-center mt-1">
                  <Clock className="w-3 h-3 mr-1" />
                  Faster than usual
                </p>
              </div>
              <div className="h-12 w-12 bg-orange-100 rounded-lg flex items-center justify-center">
                <RefreshCw className="w-6 h-6 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="methods" className="w-full">
        <TabsList className="grid w-full grid-cols-1 sm:grid-cols-3">
          <TabsTrigger value="methods">Payment Methods</TabsTrigger>
          <TabsTrigger value="history">Payout History</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        {/* Payment Methods Tab */}
        <TabsContent value="methods" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Your Payment Methods</CardTitle>
              <Button variant="outline" size="sm" onClick={() => setShowNewPaymentMethod(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add Method
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {paymentMethods.map((method) => (
                  <div key={method.id} className={`p-4 border rounded-lg ${method.default ? 'border-blue-200 bg-blue-50' : ''}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-gray-100 rounded-lg flex items-center justify-center">
                          {getMethodIcon(method.type)}
                        </div>
                        <div>
                          <p className="font-medium">{method.label}</p>
                          <p className="text-sm text-muted-foreground">{method.details}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {method.verified ? (
                          <Badge className="bg-green-100 text-green-700">Verified</Badge>
                        ) : (
                          <Badge className="bg-yellow-100 text-yellow-700">Pending</Badge>
                        )}
                        {method.default && <Badge variant="secondary">Default</Badge>}
                        <Button variant="ghost" size="sm">
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm">
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {paymentMethods.filter(m => !m.verified).length > 0 && (
                <Alert className="mt-4">
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    You have {paymentMethods.filter(m => !m.verified).length} payment method(s) pending verification. 
                    Complete verification to enable payouts to these methods.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Supported Payment Methods */}
          <Card>
            <CardHeader>
              <CardTitle>Supported Payment Methods</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <Smartphone className="w-8 h-8 text-blue-500" />
                  <div>
                    <p className="font-medium">Mobile Money</p>
                    <p className="text-sm text-muted-foreground">MTN, Airtel, Zamtel</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <Building2 className="w-8 h-8 text-green-500" />
                  <div>
                    <p className="font-medium">Bank Transfer</p>
                    <p className="text-sm text-muted-foreground">Local banks</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <Banknote className="w-8 h-8 text-orange-500" />
                  <div>
                    <p className="font-medium">Cryptocurrency</p>
                    <p className="text-sm text-muted-foreground">Bitcoin, USDT</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <CreditCard className="w-8 h-8 text-purple-500" />
                  <div>
                    <p className="font-medium">Digital Wallets</p>
                    <p className="text-sm text-muted-foreground">PayPal, Skrill</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Payout History Tab */}
        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Payouts</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {payoutHistory.map((payout) => (
                  <div key={payout.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(payout.status)}
                      <div>
                        <p className="font-medium">ZMW {payout.amount.toFixed(2)} via {payout.method}</p>
                        <p className="text-sm text-muted-foreground">
                          Requested: {payout.requestDate}
                          {payout.processedDate && ` • Processed: ${payout.processedDate}`}
                        </p>
                        <p className="text-xs text-muted-foreground">Ref: {payout.reference}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        {getStatusBadge(payout.status)}
                        {payout.fees > 0 && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Fee: ZMW {payout.fees.toFixed(2)}
                          </p>
                        )}
                      </div>
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Payout Statistics */}
          <Card>
            <CardHeader>
              <CardTitle>Payout Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-medium mb-3">Total Payouts</h3>
                  <div className="text-2xl font-bold text-green-600 mb-2">
                    ZMW {payoutStats.totalPayouts.toLocaleString()}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Total fees paid: ZMW {payoutStats.totalFees.toFixed(2)}
                  </p>
                </div>
                <div>
                  <h3 className="font-medium mb-3">Success Metrics</h3>
                  <div className="space-y-2">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Success Rate</span>
                        <span>{payoutStats.successRate}%</span>
                      </div>
                      <Progress value={payoutStats.successRate} className="h-2" />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="w-5 h-5" />
                Payout Settings
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="minimum">Minimum Payout Amount (ZMW)</Label>
                <Input id="minimum" value={minimumPayout} readOnly />
                <p className="text-sm text-muted-foreground">
                  This is the minimum amount you can request for payout
                </p>
              </div>

              <div className="space-y-2">
                <Label>Auto-payout Settings</Label>
                <Select defaultValue="manual">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual payouts only</SelectItem>
                    <SelectItem value="weekly">Weekly auto-payout</SelectItem>
                    <SelectItem value="monthly">Monthly auto-payout</SelectItem>
                    <SelectItem value="threshold">When balance reaches threshold</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="notifications">Payout Notifications</Label>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" defaultChecked />
                    <label className="text-sm">Email notifications for payout updates</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" defaultChecked />
                    <label className="text-sm">SMS notifications for completed payouts</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" />
                    <label className="text-sm">Push notifications for failed payouts</label>
                  </div>
                </div>
              </div>

              <Button>Save Settings</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Security & Verification</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert>
                <Shield className="h-4 w-4" />
                <AlertDescription>
                  Two-factor authentication is required for all payout requests above ZMW 500.
                </AlertDescription>
              </Alert>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <div>
                      <p className="font-medium">Identity Verified</p>
                      <p className="text-sm text-muted-foreground">KYC completed</p>
                    </div>
                  </div>
                  <Badge className="bg-green-100 text-green-700">Verified</Badge>
                </div>

                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <div>
                      <p className="font-medium">Phone Verified</p>
                      <p className="text-sm text-muted-foreground">+260 97 123 4567</p>
                    </div>
                  </div>
                  <Badge className="bg-green-100 text-green-700">Verified</Badge>
                </div>

                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-yellow-500" />
                    <div>
                      <p className="font-medium">2FA Authentication</p>
                      <p className="text-sm text-muted-foreground">Recommended for security</p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm">Enable</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AffiliatePayouts;

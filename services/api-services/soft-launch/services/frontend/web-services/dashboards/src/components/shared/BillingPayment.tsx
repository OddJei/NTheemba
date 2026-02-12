import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { 
  CreditCard, 
  Smartphone, 
  CheckCircle, 
  AlertTriangle,
  Loader2,
  ArrowLeft
} from "lucide-react";

interface BillingPaymentProps {
  planName: string;
  amount: number;
  billingCycle: 'monthly' | 'yearly';
  onBack: () => void;
  onPaymentSuccess: () => void;
}

const BillingPayment: React.FC<BillingPaymentProps> = ({
  planName,
  amount,
  billingCycle,
  onBack,
  onPaymentSuccess
}) => {
  const [paymentMethod, setPaymentMethod] = useState('mtn-momo');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const paymentMethods = [
    {
      id: 'mtn-momo',
      name: 'MTN Mobile Money',
      icon: <Smartphone className="w-5 h-5" />,
      description: 'Pay using your MTN MoMo wallet'
    },
    {
      id: 'airtel-money',
      name: 'Airtel Money',
      icon: <Smartphone className="w-5 h-5" />,
      description: 'Pay using your Airtel Money wallet'
    },
    {
      id: 'zamtel-kwacha',
      name: 'Zamtel Kwacha',
      icon: <Smartphone className="w-5 h-5" />,
      description: 'Pay using your Zamtel Kwacha wallet'
    }
  ];

  const handlePayment = async () => {
    if (!phoneNumber.trim()) {
      alert('Please enter your phone number');
      return;
    }

    setIsProcessing(true);
    
    try {
      // Simulate payment processing
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Mock successful payment
      setPaymentStatus('success');
      setTimeout(() => {
        onPaymentSuccess();
      }, 2000);
      
    } catch (error) {
      setPaymentStatus('error');
    } finally {
      setIsProcessing(false);
    }
  };

  if (paymentStatus === 'success') {
    return (
      <Card className="max-w-md mx-auto">
        <CardContent className="p-6 text-center space-y-4">
          <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>
          <h3 className="text-xl font-bold">Payment Successful!</h3>
          <p className="text-muted-foreground">
            Your {planName} subscription has been activated successfully.
          </p>
          <Badge className="bg-green-100 text-green-800">
            ZMW {amount} paid via {paymentMethods.find(p => p.id === paymentMethod)?.name}
          </Badge>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Button variant="ghost" onClick={onBack} size="sm">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <div>
          <h2 className="text-xl font-bold">Complete Payment</h2>
          <p className="text-muted-foreground text-sm">
            Subscribe to {planName} - {billingCycle} billing
          </p>
        </div>
      </div>

      {/* Order Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Order Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between">
            <span>{planName} Plan ({billingCycle})</span>
            <span className="font-semibold">ZMW {amount}</span>
          </div>
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Billing Cycle</span>
            <span>Every {billingCycle === 'monthly' ? 'month' : 'year'}</span>
          </div>
          <hr />
          <div className="flex justify-between font-bold text-lg">
            <span>Total</span>
            <span>ZMW {amount}</span>
          </div>
        </CardContent>
      </Card>

      {/* Payment Methods */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Select Payment Method</CardTitle>
          <CardDescription>
            Choose your preferred mobile money provider
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <RadioGroup value={paymentMethod} onValueChange={setPaymentMethod}>
            {paymentMethods.map((method) => (
              <div key={method.id} className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-accent">
                <RadioGroupItem value={method.id} id={method.id} />
                <Label htmlFor={method.id} className="flex items-center space-x-3 cursor-pointer flex-1">
                  {method.icon}
                  <div>
                    <div className="font-medium">{method.name}</div>
                    <div className="text-sm text-muted-foreground">{method.description}</div>
                  </div>
                </Label>
              </div>
            ))}
          </RadioGroup>

          {/* Phone Number Input */}
          <div className="space-y-2 mt-4">
            <Label htmlFor="phone">Phone Number</Label>
            <Input
              id="phone"
              type="tel"
              placeholder="e.g., 0977123456"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Enter the phone number associated with your mobile money account
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Payment Confirmation */}
      <Card>
        <CardContent className="p-6">
          <Alert className="mb-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-sm">
              You will receive a prompt on your phone to authorize the payment of ZMW {amount}.
            </AlertDescription>
          </Alert>

          <Button 
            onClick={handlePayment}
            disabled={isProcessing || !phoneNumber.trim()}
            className="w-full"
            size="lg"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing Payment...
              </>
            ) : (
              <>
                <CreditCard className="w-4 h-4 mr-2" />
                Pay ZMW {amount}
              </>
            )}
          </Button>

            <p className="text-xs text-center text-muted-foreground mt-3">
            Secure payment powered by NTheemba. Your payment information is encrypted and protected.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default BillingPayment;

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Building2, Users, ArrowLeft } from "lucide-react";

const Login = () => {
  const [role, setRole] = useState<'msme' | 'affiliate' | null>(null);
  const navigate = useNavigate();

  const handleLogin = (userRole: 'msme' | 'affiliate') => {
    // Simple navigation - in real app, this would handle authentication
    navigate(`/${userRole}`);
  };

  if (!role) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-primary/5 to-accent/10 flex items-center justify-center p-4">
        <div className="w-full max-w-md space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold tracking-tight">Welcome Back</h1>
            <p className="text-muted-foreground">Choose your role to continue</p>
          </div>
          
          <div className="grid gap-4">
            <Card 
              className="cursor-pointer hover:shadow-lg transition-all hover:scale-105 border-2 hover:border-primary/50"
              onClick={() => setRole('msme')}
            >
              <CardHeader className="text-center pb-2">
                <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                  <Building2 className="w-8 h-8 text-primary" />
                </div>
                <CardTitle>I'm an MSME</CardTitle>
                <CardDescription>
                  Manage your business, products, and growth
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button className="w-full" size="lg">
                  Continue as Business
                </Button>
              </CardContent>
            </Card>

            <Card 
              className="cursor-pointer hover:shadow-lg transition-all hover:scale-105 border-2 hover:border-accent/50"
              onClick={() => setRole('affiliate')}
            >
              <CardHeader className="text-center pb-2">
                <div className="mx-auto w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-4">
                  <Users className="w-8 h-8 text-accent-foreground" />
                </div>
                <CardTitle>I'm an Affiliate</CardTitle>
                <CardDescription>
                  Promote businesses and earn commissions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="secondary" className="w-full" size="lg">
                  Continue as Affiliate
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 to-accent/10 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <Button 
            variant="ghost" 
            size="sm" 
            className="w-fit mb-4"
            onClick={() => setRole(null)}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <CardTitle>
            Sign in as {role === 'msme' ? 'MSME' : 'Affiliate'}
          </CardTitle>
          <CardDescription>
            Enter your credentials to access your dashboard
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="your@email.com" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" />
          </div>
          <Button 
            className="w-full" 
            size="lg"
            onClick={() => handleLogin(role)}
          >
            Sign In
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Building2, Users, TrendingUp } from "lucide-react";

const Index = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-accent/5">
      {/* Header */}
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <img 
              src="/ntheemba-logo-compact.svg" 
              alt="NTheemba" 
              className="w-8 h-8"
            />
            <h1 className="text-2xl font-bold">NTheemba</h1>
          </div>
          <Button onClick={() => navigate('/login')}>
            Get Started
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h2 className="text-5xl font-bold mb-6 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Empowering MSMEs Through Smart Partnerships
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto mb-8">
            Connect micro, small & medium enterprises with influencers and affiliates. 
            Grow your business or monetize your influence with our powerful platform.
          </p>
          <div className="flex gap-4 justify-center">
            <Button size="lg" onClick={() => navigate('/login')}>
              Start Your Journey
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate('/subscription-demo')}>
              View Demo
            </Button>
            <Button size="lg" variant="ghost">
              Learn More
            </Button>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          <Card className="text-center hover:shadow-lg transition-all">
            <CardHeader>
              <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Building2 className="w-8 h-8 text-primary" />
              </div>
              <CardTitle>For MSMEs</CardTitle>
              <CardDescription>
                Complete business management and growth tools
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-left space-y-2 text-sm text-muted-foreground">
                <li>• Product & inventory management</li>
                <li>• Sales analytics & insights</li>
                <li>• Brand building tools</li>
                <li>• Campaign automation</li>
              </ul>
              <Button 
                className="w-full mt-4" 
                onClick={() => navigate('/login')}
              >
                Get Started as MSME
              </Button>
            </CardContent>
          </Card>

          <Card className="text-center hover:shadow-lg transition-all">
            <CardHeader>
              <div className="mx-auto w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-4">
                <Users className="w-8 h-8 text-accent-foreground" />
              </div>
              <CardTitle>For Affiliates</CardTitle>
              <CardDescription>
                Monetize your influence and help businesses grow
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-left space-y-2 text-sm text-muted-foreground">
                <li>• Campaign management</li>
                <li>• Content creation tools</li>
                <li>• Earnings tracking</li>
                <li>• Performance leaderboards</li>
              </ul>
              <Button 
                variant="secondary" 
                className="w-full mt-4"
                onClick={() => navigate('/login')}
              >
                Become an Affiliate
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Stats Section */}
        <div className="mt-16 text-center">
          <div className="inline-flex items-center space-x-2 bg-primary/10 px-4 py-2 rounded-full mb-8">
            <TrendingUp className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium">Growing Fast</span>
          </div>
          
          <div className="grid grid-cols-3 gap-8 max-w-2xl mx-auto">
            <div>
              <div className="text-3xl font-bold text-primary">1,000+</div>
              <div className="text-sm text-muted-foreground">MSMEs Connected</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">5,000+</div>
              <div className="text-sm text-muted-foreground">Active Affiliates</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-primary">ZMW 2Cr+</div>
              <div className="text-sm text-muted-foreground">Revenue Generated</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
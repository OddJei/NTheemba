import { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { 
  Home, 
  Megaphone, 
  Palette, 
  DollarSign, 
  Trophy,
  Bell,
  User,
  LogOut,
  Wallet,
  Link2,
  Shield,
  MessageSquare,
  Crown,
  Heart,
  Menu,
  CreditCard
} from "lucide-react";

interface AffiliateLayoutProps {
  children: ReactNode;
}

const AffiliateLayout = ({ children }: AffiliateLayoutProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { path: "/affiliate", label: "Dashboard", icon: Home },
    { path: "/affiliate/campaigns", label: "My Campaigns", icon: Megaphone },
    { path: "/affiliate/links", label: "Link Generator", icon: Link2 },
    { path: "/affiliate/content", label: "Content Tools", icon: Palette },
    { path: "/affiliate/earnings", label: "Earnings", icon: DollarSign },
    { path: "/affiliate/payouts", label: "Payouts", icon: Wallet },
    { path: "/affiliate/subscription", label: "Subscription", icon: CreditCard },
    { path: "/affiliate/ubuntu-community", label: "Ubuntu Community", icon: Heart },
    { path: "/affiliate/ubuntu-subscription", label: "Ubuntu Plans", icon: Crown },
    { path: "/affiliate/notifications", label: "Notifications", icon: Bell },
    { path: "/affiliate/security", label: "Security", icon: Shield },
    { path: "/affiliate/feedback", label: "Feedback", icon: MessageSquare },
    { path: "/affiliate/leaderboards", label: "Leaderboards", icon: Trophy },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Sticky Header - Consistent with MSME */}
      <header className="sticky top-0 z-40 border-b bg-card/50 backdrop-blur">
        <div className="px-3 py-2 sm:px-4 sm:py-3">
          <div className="flex items-center justify-between">
            {/* Mobile Menu + Logo */}
            <div className="flex items-center space-x-2 sm:space-x-4">
              {/* Mobile Menu Toggle */}
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="ghost" size="sm" className="md:hidden">
                    <Menu className="w-5 h-5" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-64 p-0">
                  <div className="p-4 border-b">
                    <div className="flex items-center space-x-2">
                      <img 
                        src="/ntheemba-logo-compact.svg" 
                        alt="NTheemba" 
                        className="w-6 h-6"
                      />
                      <span className="font-semibold">Affiliate Hub</span>
                    </div>
                  </div>
                  <nav className="p-4 space-y-2">
                    {navItems.map((item) => {
                      const isActive = location.pathname === item.path;
                      const Icon = item.icon;
                      
                      return (
                        <Link
                          key={item.path}
                          to={item.path}
                          className={`flex items-center space-x-3 px-3 py-2 rounded-md transition-colors ${
                            isActive 
                              ? 'bg-accent text-accent-foreground' 
                              : 'hover:bg-accent/50'
                          }`}
                        >
                          <Icon className="w-5 h-5" />
                          <span>{item.label}</span>
                        </Link>
                      );
                    })}
                  </nav>
                </SheetContent>
              </Sheet>
              
              <img 
                src="/ntheemba-logo-compact.svg" 
                alt="NTheemba" 
                className="w-6 h-6 sm:w-8 sm:h-8"
              />
              <h1 className="text-base sm:text-xl font-bold hidden xs:block">Affiliate Hub</h1>
              <h1 className="text-base font-bold xs:hidden">Affiliate</h1>
            </div>
            
            {/* Impact Summary - Mobile Optimized */}
            <div className="flex items-center space-x-2 sm:space-x-4 text-xs sm:text-sm">
              <div className="hidden sm:flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <span className="text-muted-foreground">This Week:</span>
                  <Badge variant="secondary" className="text-xs">102 Clicks</Badge>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-muted-foreground">Earned:</span>
                  <Badge className="text-xs">ZMW 4,560</Badge>
                </div>
                <div className="flex items-center space-x-1">
                  <Bell className="w-4 h-4 text-blue-500" />
                  <span className="text-blue-600">3</span>
                </div>
              </div>
              
              {/* Mobile: Condensed stats */}
              <div className="sm:hidden flex items-center space-x-1">
                <Badge variant="secondary" className="text-xs px-1">102</Badge>
                <Badge className="text-xs px-1">ZMW 4.5K</Badge>
                <Bell className="w-4 h-4 text-blue-500" />
              </div>
            </div>

            {/* Profile Actions */}
            <div className="flex items-center space-x-1">
              <Button 
                variant="ghost" 
                size="sm" 
                className="hidden sm:flex"
                onClick={() => navigate('/affiliate/profile')}
              >
                <User className="w-4 h-4 sm:mr-2" />
                <span className="hidden sm:inline">Profile</span>
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate('/')}
              >
                <LogOut className="w-4 h-4 sm:mr-2" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Desktop Sidebar */}
        <aside className="hidden md:block w-64 border-r bg-card/30 min-h-[calc(100vh-65px)]">
          <nav className="p-4 space-y-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-md transition-colors ${
                    isActive 
                      ? 'bg-accent text-accent-foreground' 
                      : 'hover:bg-accent/50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-sm">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Main Content - Mobile First */}
        <main className="flex-1 p-3 sm:p-4 md:p-6 pb-20 md:pb-6">
          {children}
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card/95 backdrop-blur border-t z-30">
        <div className="flex items-center justify-around px-2 py-2">
          {navItems.slice(0, 5).map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex flex-col items-center space-y-1 px-2 py-2 rounded-md transition-colors min-w-0 ${
                  isActive 
                    ? 'text-accent-foreground' 
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

export default AffiliateLayout;
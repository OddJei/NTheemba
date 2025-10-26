import { ReactNode, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { 
  BarChart3, 
  Package, 
  Palette, 
  TrendingUp, 
  Megaphone, 
  Bell,
  User,
  LogOut,
  Menu,
  CreditCard,
  Crown,
  Heart
} from "lucide-react";

interface MSMELayoutProps {
  children: ReactNode;
}

const MSMELayout = ({ children }: MSMELayoutProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  // global handler: when route or hash changes, scroll to the element (if present)
  useEffect(() => {
    const scrollToHash = () => {
      try {
        if (typeof window === 'undefined') return;
        const hash = window.location.hash;
        if (!hash) return;
        const id = hash.replace('#', '');
        const el = document.getElementById(id);
        if (el) {
          setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
          (el as HTMLElement).focus?.();
        }
      } catch (e) {
        // ignore
      }
    };

    // run once for immediate navigation
    scrollToHash();

    const onHashChange = () => scrollToHash();
    window.addEventListener('hashchange', onHashChange);

    // custom event allows components to request a scroll even when location doesn't change
    const onCustomScroll = (e: Event) => {
      try {
        const detail = (e as CustomEvent)?.detail as { id?: string } | undefined;
        const id = detail?.id || window.location.hash.replace('#', '');
        if (!id) return;
        const el = document.getElementById(id);
        if (el) {
          setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
          (el as HTMLElement).focus?.();
        }
      } catch (err) {
        // ignore
      }
    };
    window.addEventListener('ntheemba:scroll-to', onCustomScroll as EventListener);

    return () => {
      window.removeEventListener('hashchange', onHashChange);
      window.removeEventListener('ntheemba:scroll-to', onCustomScroll as EventListener);
    };
  }, [location]);

  const navItems = [
    { path: "/msme", label: "Dashboard", icon: BarChart3 },
    { path: "/msme/products", label: "Products", icon: Package },
    { path: "/msme/branding", label: "Branding", icon: Palette },
    { path: "/msme/insights", label: "Insights", icon: TrendingUp },
    { path: "/msme/campaigns", label: "Campaigns", icon: Megaphone },
    { path: "/msme/subscription", label: "Subscription", icon: CreditCard },
    { path: "/msme/ubuntu-community", label: "Ubuntu Community", icon: Heart },
    { path: "/msme/ubuntu-subscription", label: "Ubuntu Plans", icon: Crown },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile-First Header */}
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
                      <span className="font-semibold">MSME Center</span>
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
                              ? 'bg-primary text-primary-foreground' 
                              : 'hover:bg-accent hover:text-accent-foreground'
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
              <h1 className="text-base sm:text-xl font-bold hidden xs:block">MSME Control Center</h1>
              <h1 className="text-base font-bold xs:hidden">MSME</h1>
            </div>
            
            {/* Mobile Stats - Condensed */}
            <div className="flex items-center space-x-2 sm:space-x-4 text-xs sm:text-sm">
              <div className="hidden sm:flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <span className="text-muted-foreground">Today:</span>
                  <Badge variant="secondary" className="text-xs">ZMW 12.3K</Badge>
                </div>
                <div className="flex items-center space-x-1">
                  <Bell className="w-4 h-4 text-orange-500" />
                  <span className="text-orange-600">3</span>
                </div>
              </div>
              
              {/* Mobile: Just show notifications */}
              <div className="sm:hidden flex items-center space-x-1">
                <Badge variant="secondary" className="text-xs px-1">ZMW 12K</Badge>
                <Bell className="w-4 h-4 text-orange-500" />
              </div>
            </div>

            {/* Profile Actions */}
            <div className="flex items-center space-x-1">
              <Button 
                variant="ghost" 
                size="sm" 
                className="hidden sm:flex"
                onClick={() => navigate('/msme/profile')}
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
                      ? 'bg-primary text-primary-foreground' 
                      : 'hover:bg-accent hover:text-accent-foreground'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.label}</span>
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
                    ? 'text-primary' 
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

export default MSMELayout;
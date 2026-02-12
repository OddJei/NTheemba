import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trophy, Medal, Award } from "lucide-react";

const AffiliateLeaderboards = () => {
  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <h1 className="text-2xl sm:text-3xl font-bold">Leaderboards & Incentives</h1>
      
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center text-lg sm:text-xl">
            <Trophy className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-yellow-500" />
            Monthly Top 10
          </CardTitle>
          <CardDescription className="text-sm">Top performers this month</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 sm:space-y-3">
            {[1, 2, 3, 4, 5].map((rank) => (
              <div key={rank} className="flex items-center justify-between p-2 sm:p-3 rounded-lg bg-muted/50">
                <div className="flex items-center space-x-2 sm:space-x-3 flex-1">
                  <div className={`w-6 h-6 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-xs sm:text-sm ${
                    rank === 1 ? 'bg-yellow-100 text-yellow-800' :
                    rank === 2 ? 'bg-gray-100 text-gray-800' :
                    rank === 3 ? 'bg-orange-100 text-orange-800' :
                    'bg-muted text-muted-foreground'
                  }`}>
                    {rank}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm sm:text-base truncate">
                      {rank === 4 ? 'Priya S. (You)' : `Affiliate ${rank}`}
                    </div>
                    <div className="text-xs sm:text-sm text-muted-foreground">
                      {Math.floor(Math.random() * 50) + 10} MSMEs helped
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-medium text-sm sm:text-base">ZMW {(Math.random() * 20000 + 5000).toFixed(0)}</div>
                  <div className="text-xs text-muted-foreground">earned</div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center text-lg sm:text-xl">
              <Medal className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
              Your Milestones
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 sm:space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm sm:text-base">First Sale</span>
                <Badge className="bg-green-100 text-green-800 text-xs">✓ Completed</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm sm:text-base">10 Sales</span>
                <Badge className="bg-green-100 text-green-800 text-xs">✓ Completed</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm sm:text-base">ZMW 10K Earnings</span>
                <Badge className="bg-green-100 text-green-800 text-xs">✓ Completed</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm sm:text-base">50 Sales</span>
                <Badge variant="outline" className="text-xs">In Progress (23/50)</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Tier Progress</CardTitle>
            <CardDescription className="text-sm">Advance to unlock better rewards</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 sm:space-y-4">
              <div className="flex justify-between items-center">
                <span className="font-medium text-sm sm:text-base">Silver Tier</span>
                <Badge className="text-xs">Current</Badge>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div className="bg-primary h-2 rounded-full" style={{width: '65%'}}></div>
              </div>
              <div className="text-xs sm:text-sm text-muted-foreground">
                65% to Gold Tier (ZMW 25,000 total earnings)
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AffiliateLeaderboards;
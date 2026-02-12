import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Filter, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

const AffiliateCampaigns = () => {
  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <h1 className="text-2xl sm:text-3xl font-bold">My Campaigns</h1>
        <Button className="w-full sm:w-auto">
          <Plus className="w-4 h-4 mr-2" />
          Join Campaign
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search campaigns..." className="pl-10" />
        </div>
        <Button variant="outline" className="w-full sm:w-auto">
          <Filter className="w-4 h-4 mr-2" />
          Filter by Industry
        </Button>
      </div>

      <div className="grid gap-3 sm:gap-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2">
                <div className="flex-1">
                  <CardTitle className="text-lg sm:text-xl">Handwoven Textiles Campaign</CardTitle>
                  <CardDescription className="text-sm">Traditional Indian textiles promotion</CardDescription>
                </div>
                <Badge className="bg-green-100 text-green-800 w-fit">Active</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 text-center">
                <div className="p-2 sm:p-0">
                  <div className="text-lg sm:text-xl font-bold">ZMW 250</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Per Sale</div>
                </div>
                <div className="p-2 sm:p-0">
                  <div className="text-lg sm:text-xl font-bold">45</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Clicks</div>
                </div>
                <div className="p-2 sm:p-0">
                  <div className="text-lg sm:text-xl font-bold">3</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Sales</div>
                </div>
                <div className="p-2 sm:p-0">
                  <div className="text-lg sm:text-xl font-bold text-green-600">ZMW 750</div>
                  <div className="text-xs sm:text-sm text-muted-foreground">Earned</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default AffiliateCampaigns;
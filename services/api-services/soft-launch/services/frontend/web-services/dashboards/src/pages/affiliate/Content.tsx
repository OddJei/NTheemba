import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, Share2, Download } from "lucide-react";

const AffiliateContent = () => {
  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <h1 className="text-2xl sm:text-3xl font-bold">Content Tools</h1>
      
      <div className="grid gap-4 sm:gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Auto-Copy Captions</CardTitle>
            <CardDescription className="text-sm">Ready-to-use captions with hashtags</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-muted p-3 sm:p-4 rounded-lg mb-4">
              <p className="text-xs sm:text-sm">🌟 Discover authentic handwoven textiles! Support local artisans while adding elegance to your wardrobe. #HandwovenTextiles #SupportLocal #TraditionalCrafts #MSMESupport</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <Button size="sm" className="w-full sm:w-auto">
                <Copy className="w-4 h-4 mr-2" />
                Copy Caption
              </Button>
              <Button size="sm" variant="outline" className="w-full sm:w-auto">
                <Share2 className="w-4 h-4 mr-2" />
                Share Now
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Visual Templates</CardTitle>
            <CardDescription className="text-sm">Swipeable carousel of poster & reel templates</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                  <span className="text-xs sm:text-sm">Template {i}</span>
                </div>
              ))}
            </div>
            <Button className="w-full mt-4">
              <Download className="w-4 h-4 mr-2" />
              Download Selected
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AffiliateContent;
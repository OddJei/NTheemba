import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Separator } from '../../components/ui/separator';
import { Copy, QrCode, Share2, ExternalLink, Filter, Calendar, Smartphone, Monitor, Tablet } from 'lucide-react';
import { Alert, AlertDescription } from '../../components/ui/alert';

const LinkGenerator = () => {
  const [selectedProduct, setSelectedProduct] = useState('');
  const [selectedCampaign, setSelectedCampaign] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [generatedLink, setGeneratedLink] = useState('');
  const [showQR, setShowQR] = useState(false);
  const [message, setMessage] = useState('');
  const [clickData, setClickData] = useState([
    {
      id: 1,
      timestamp: '2025-09-01T10:30:00Z',
      source: 'WhatsApp',
      device: 'mobile',
      location: 'Lusaka',
      converted: true
    },
    {
      id: 2,
      timestamp: '2025-09-01T09:15:00Z',
      source: 'Facebook',
      device: 'desktop',
      location: 'Ndola',
      converted: false
    },
    {
      id: 3,
      timestamp: '2025-09-01T08:45:00Z',
      source: 'Direct',
      device: 'tablet',
      location: 'Kitwe',
      converted: true
    }
  ]);
  const [filterSource, setFilterSource] = useState('all');
  const [filterDevice, setFilterDevice] = useState('all');

  const products = [
    { id: 'textile-1', name: 'Handwoven Textiles', category: 'Traditional Crafts' },
    { id: 'jewelry-1', name: 'Beaded Jewelry', category: 'Accessories' },
    { id: 'pottery-1', name: 'Clay Pottery', category: 'Home Decor' },
    { id: 'woodcraft-1', name: 'Wooden Sculptures', category: 'Art' }
  ];

  const campaigns = [
    { id: 'summer-2025', name: 'Summer Collection 2025', commission: '15%' },
    { id: 'heritage-month', name: 'Heritage Month Special', commission: '20%' },
    { id: 'artisan-spotlight', name: 'Artisan Spotlight', commission: '12%' }
  ];

  const generateLink = () => {
    if (!selectedProduct || !selectedCampaign) {
      setMessage('Please select both a product and campaign');
      return;
    }

  const baseUrl = 'https://ntheemba.com/shop';
    const affiliateId = 'AFF123456';
    const linkId = `${selectedProduct}_${selectedCampaign}_${Date.now()}`;
    
    const generatedUrl = `${baseUrl}/${selectedProduct}?aff=${affiliateId}&campaign=${selectedCampaign}&link_id=${linkId}`;
    setGeneratedLink(generatedUrl);
    setMessage('Link generated successfully!');
    setTimeout(() => setMessage(''), 3000);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setMessage('Copied to clipboard!');
    setTimeout(() => setMessage(''), 2000);
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getDeviceIcon = (device) => {
    switch (device) {
      case 'mobile': return <Smartphone className="w-4 h-4" />;
      case 'tablet': return <Tablet className="w-4 h-4" />;
      default: return <Monitor className="w-4 h-4" />;
    }
  };

  const filteredClickData = clickData.filter(click => {
    const sourceMatch = filterSource === 'all' || click.source.toLowerCase() === filterSource.toLowerCase();
    const deviceMatch = filterDevice === 'all' || click.device === filterDevice;
    return sourceMatch && deviceMatch;
  });

  return (
    <div className="space-y-4 sm:space-y-6 p-2 sm:p-4">
      <h1 className="text-2xl sm:text-3xl font-bold">Link & Campaign Tools</h1>
      
      {message && (
        <Alert>
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Link Generator */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Generate Affiliate Link</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="product">Select Product</Label>
              <Select value={selectedProduct} onValueChange={setSelectedProduct}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a product..." />
                </SelectTrigger>
                <SelectContent>
                  {products.map(product => (
                    <SelectItem key={product.id} value={product.id}>
                      {product.name} ({product.category})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="campaign">Select Campaign</Label>
              <Select value={selectedCampaign} onValueChange={setSelectedCampaign}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a campaign..." />
                </SelectTrigger>
                <SelectContent>
                  {campaigns.map(campaign => (
                    <SelectItem key={campaign.id} value={campaign.id}>
                      {campaign.name} ({campaign.commission} commission)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="message">Custom Message (Optional)</Label>
              <Textarea
                id="message"
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                placeholder="Add a personal message to accompany your link..."
                rows={3}
              />
            </div>

            <Button onClick={generateLink} className="w-full">
              Generate Link
            </Button>

            {generatedLink && (
              <div className="space-y-3 p-3 bg-muted rounded-lg">
                <div>
                  <Label className="text-sm font-medium">Generated Link:</Label>
                  <div className="flex items-center gap-2 mt-1">
                    <Input 
                      value={generatedLink} 
                      readOnly 
                      className="text-xs"
                    />
                    <Button size="sm" variant="outline" onClick={() => copyToClipboard(generatedLink)}>
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setShowQR(!showQR)}>
                    <QrCode className="w-4 h-4 mr-2" />
                    {showQR ? 'Hide' : 'Show'} QR Code
                  </Button>
                  <Button size="sm" variant="outline">
                    <Share2 className="w-4 h-4 mr-2" />
                    Share
                  </Button>
                </div>

                {showQR && (
                  <div className="bg-white p-4 rounded border-2 border-dashed text-center">
                    <div className="w-32 h-32 mx-auto bg-gray-200 rounded flex items-center justify-center">
                      <QrCode className="w-16 h-16 text-gray-400" />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">QR Code for easy sharing</p>
                  </div>
                )}

                {customMessage && (
                  <div>
                    <Label className="text-sm font-medium">Your Message:</Label>
                    <div className="bg-white p-2 rounded border mt-1 text-sm">
                      {customMessage}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Generated Links History */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Recent Links</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="p-3 border rounded-lg">
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">Handwoven Textiles - Summer Collection</div>
                      <div className="text-xs text-muted-foreground">Generated 2 hours ago</div>
                      <div className="text-xs text-muted-foreground truncate mt-1">
                        https://ntheemba.com/shop/textile-1?aff=AFF123456...
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost">
                        <Copy className="w-3 h-3" />
                      </Button>
                      <Button size="sm" variant="ghost">
                        <ExternalLink className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-2">
                    <Badge variant="secondary" className="text-xs">24 clicks</Badge>
                    <Badge variant="outline" className="text-xs">3 conversions</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Click Tracking Dashboard */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
            <CardTitle className="text-lg sm:text-xl">Click Tracking Dashboard</CardTitle>
            <div className="flex flex-col sm:flex-row gap-2">
              <Select value={filterSource} onValueChange={setFilterSource}>
                <SelectTrigger className="w-full sm:w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sources</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                  <SelectItem value="facebook">Facebook</SelectItem>
                  <SelectItem value="direct">Direct</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterDevice} onValueChange={setFilterDevice}>
                <SelectTrigger className="w-full sm:w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Devices</SelectItem>
                  <SelectItem value="mobile">Mobile</SelectItem>
                  <SelectItem value="desktop">Desktop</SelectItem>
                  <SelectItem value="tablet">Tablet</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {filteredClickData.map(click => (
              <div key={click.id} className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-3 border rounded-lg gap-2">
                <div className="flex items-center gap-3">
                  {getDeviceIcon(click.device)}
                  <div>
                    <div className="font-medium text-sm">{formatTimestamp(click.timestamp)}</div>
                    <div className="text-xs text-muted-foreground">{click.location}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">{click.source}</Badge>
                  <Badge variant="outline" className="text-xs">{click.device}</Badge>
                  <Badge 
                    className={`text-xs ${click.converted ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
                  >
                    {click.converted ? 'Converted' : 'No Sale'}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
          
          {filteredClickData.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              No clicks match your current filters
            </div>
          )}
          
          <Separator className="my-4" />
          
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-lg font-bold">{clickData.length}</div>
              <div className="text-xs text-muted-foreground">Total Clicks</div>
            </div>
            <div>
              <div className="text-lg font-bold text-green-600">{clickData.filter(c => c.converted).length}</div>
              <div className="text-xs text-muted-foreground">Conversions</div>
            </div>
            <div>
              <div className="text-lg font-bold">
                {Math.round((clickData.filter(c => c.converted).length / clickData.length) * 100)}%
              </div>
              <div className="text-xs text-muted-foreground">Conversion Rate</div>
            </div>
            <div>
              <div className="text-lg font-bold">ZMW {(clickData.filter(c => c.converted).length * 250).toFixed(0)}</div>
              <div className="text-xs text-muted-foreground">Est. Earnings</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Spam Prevention Alert */}
      <Alert>
        <AlertDescription className="flex items-center gap-2">
          <span>🛡️</span>
          <span className="text-sm">
            <strong>Spam Protection Active:</strong> Duplicate clicks from the same IP within 24 hours are automatically filtered. 
            Suspicious activity is flagged for review.
          </span>
        </AlertDescription>
      </Alert>
    </div>
  );
};

export default LinkGenerator;

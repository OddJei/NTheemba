import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Shield, Lock, Eye, User, Database, Mail } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function Privacy() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-white/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            className="touch-target"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-green-600" />
            <h1 className="text-xl font-bold text-gray-900">Privacy Policy</h1>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="mb-6">
          <p className="text-sm text-gray-600">Last updated: February 20, 2026</p>
        </div>

        <div className="space-y-6">
          {/* Introduction */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-green-600" />
                Introduction
              </CardTitle>
            </CardHeader>
            <CardContent className="prose prose-sm max-w-none">
              <p className="text-gray-700 leading-relaxed">
                At NTheemba, we are committed to protecting your privacy and ensuring you have a
                positive experience on our platform. This Privacy Policy explains how we collect,
                use, disclose, and otherwise process your personal information.
              </p>
            </CardContent>
          </Card>

          {/* Information We Collect */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5 text-green-600" />
                1. Information We Collect
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <div>
                <h3 className="font-semibold mb-2">1.1 Account Information</h3>
                <p className="leading-relaxed">
                  When you create an account, we collect information such as your name, email
                  address, phone number, location, and any other information you provide during
                  registration.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">1.2 Transaction Information</h3>
                <p className="leading-relaxed">
                  We collect information about your transactions on NTheemba, including order
                  details, payment information, shipping addresses, and transaction history.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">1.3 Communications</h3>
                <p className="leading-relaxed">
                  When you contact us or interact with other users through our platform, we
                  collect and store those communications to improve our services and customer
                  support.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">1.4 Technical Information</h3>
                <p className="leading-relaxed">
                  We automatically collect information about your device and how you interact with
                  our platform, including IP address, browser type, pages visited, and timestamps.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* How We Use Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5 text-green-600" />
                2. How We Use Your Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>We use the information we collect to:</p>
              <ul className="list-disc list-inside space-y-2">
                <li>Create and maintain your account</li>
                <li>Process transactions and send related information</li>
                <li>Send transactional and marketing communications</li>
                <li>Provide customer support and respond to your inquiries</li>
                <li>Improve our platform and develop new features</li>
                <li>Monitor and analyze trends, usage, and activities</li>
                <li>Detect, investigate, and prevent fraudulent activities</li>
                <li>Comply with legal obligations</li>
              </ul>
            </CardContent>
          </Card>

          {/* Data Security */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-green-600" />
                3. Data Security
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <div>
                <h3 className="font-semibold mb-2">3.1 Security Measures</h3>
                <p className="leading-relaxed">
                  We implement reasonable technical, physical, and administrative safeguards to
                  protect your personal information from unauthorized access, alteration, and
                  destruction. However, no method of transmission over the internet is 100% secure.
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">3.2 Data Retention</h3>
                <p className="leading-relaxed">
                  We retain your personal information for as long as necessary to provide our
                  services and fulfill the purposes outlined in this Privacy Policy, unless a
                  longer retention period is required by law.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Sharing Information */}
          <Card>
            <CardHeader>
              <CardTitle>4. Sharing Your Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>We may share your information with:</p>
              <ul className="list-disc list-inside space-y-2">
                <li>Service providers who assist us in operating our platform</li>
                <li>Business partners with your consent</li>
                <li>Law enforcement when required by law</li>
                <li>Other parties in connection with company transactions</li>
              </ul>
              <p className="mt-4">
                We do not sell, trade, or rent your personal information to third parties without
                your consent.
              </p>
            </CardContent>
          </Card>

          {/* Your Rights */}
          <Card>
            <CardHeader>
              <CardTitle>5. Your Privacy Rights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>Depending on your location, you may have the right to:</p>
              <ul className="list-disc list-inside space-y-2">
                <li>Access the personal information we hold about you</li>
                <li>Request correction of inaccurate information</li>
                <li>Request deletion of your information</li>
                <li>Opt-out of marketing communications</li>
                <li>Data portability</li>
              </ul>
              <p className="mt-4">
                To exercise these rights, please contact us using the information provided in the
                Contact Us section below.
              </p>
            </CardContent>
          </Card>

          {/* Cookies */}
          <Card>
            <CardHeader>
              <CardTitle>6. Cookies and Tracking Technologies</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>
                We use cookies and similar tracking technologies to enhance your browsing
                experience, remember your preferences, and understand how you use our platform.
                You can control cookie settings through your browser preferences.
              </p>
            </CardContent>
          </Card>

          {/* Third-Party Links */}
          <Card>
            <CardHeader>
              <CardTitle>7. Third-Party Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>
                Our platform may contain links to third-party websites. We are not responsible
                for the privacy practices of those sites. We encourage you to read the privacy
                policies of any third-party sites you visit.
              </p>
            </CardContent>
          </Card>

          {/* Changes to Privacy Policy */}
          <Card>
            <CardHeader>
              <CardTitle>8. Changes to This Privacy Policy</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>
                We may update this Privacy Policy from time to time to reflect changes in our
                practices, technology, legal requirements, and other factors. We will notify you
                of material changes by updating the "Last updated" date at the top of this policy.
              </p>
            </CardContent>
          </Card>

          {/* Contact Us */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="w-5 h-5 text-green-600" />
                9. Contact Us
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-gray-700">
              <p>
                If you have questions about this Privacy Policy or our privacy practices, please
                contact us at:
              </p>
              <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                <p className="font-semibold">NTheemba Privacy Team</p>
                <p>Email: privacy@ntheemba.com</p>
                <p>Address: Lusaka, Zambia</p>
                <p>Response time: We aim to respond within 30 days</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Footer Spacing */}
        <div className="mt-12 pt-8 border-t border-gray-200 text-center text-sm text-gray-600">
          <p>
            Your privacy is important to us. If you have any questions, please don't hesitate
            to contact us.
          </p>
        </div>
      </main>
    </div>
  );
}
